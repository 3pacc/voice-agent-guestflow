import logging
from fastrtc import ReplyOnPause, Stream, AsyncStreamHandler
from src.stt.mistral_stt import MistralRealtimeSTT
from src.tts.inworld_tts import InworldTTS
from src.llm.vllm_client import VllmClient
from src.agent.booking_graph import booking_agent
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

class HotelAgentOrchestrator(AsyncStreamHandler):
    """
    FastRTC orchestration class.
    Handles Voice Activity Detection (VAD) to trigger Turn-based responses or interruptions.
    """
    def __init__(self):
        super().__init__()
        self.stt = MistralRealtimeSTT()
        self.tts = InworldTTS()
        self.llm = VllmClient()
        
        # Initial State
        self.initial_state = {
            "messages": [],
            "stage": "greeting",
            "check_in_date": None,
            "check_out_date": None,
            "guests": None,
            "room_available": None
        }
        self.state = self.initial_state.copy()
        
        # Audio generation control flag
        self.is_speaking = False

    async def copy_state(self):
        return self.state.copy()

    async def interrupt(self):
        """
        Called when FastRTC's VAD detects user speech while the agent is speaking.
        """
        logger.warning("User barge-in detected! Stopping audio and resetting state.")
        self.is_speaking = False
        
        # FastRTC handles stream cancellation intrinsically, 
        # but we can explicitly reset the graph context if the user completely changes topic.
        # For simplicity, we just clear the last AI message if it was interrupted mid-stream.
        # (A true robust implementation might use LangGraph checkpoints)

    async def process(self, audio_chunk: bytes):
        """
        FastRTC implicitly detects speech pause.
        When a pause occurs, this method is triggered with the spoken audio chunk.
        """
        logger.info("Processing user audio chunk via STT...")
        
        # 1. Transcribe audio
        user_text = await self.stt.transcribe_stream(audio_chunk)
        logger.info(f"User said: {user_text}")
        
        if not user_text:
            return
            
        # 2. Update agent state
        self.state["messages"].append(HumanMessage(content=user_text))
        
        # 3. Brain (LangGraph / LLM)
        new_state = await booking_agent.ainvoke(self.state)
        self.state.update(new_state)
        
        # Flag speaking state
        self.is_speaking = True
        
        # Determine AI response via streaming vLLM
        text_stream = self.llm.generate_response_stream(
            [{"role": m.type, "content": m.content} for m in self.state["messages"]]
        )

        # 4. Synthesize to audio and yield
        # The true implementation using FastRTC would yield numpy arrays or bytes back to the stream
        async for synthesized_chunk in self.tts.stream_tts(text_stream):
            if not self.is_speaking:
                logger.info("Audio synthesis interrupted.")
                break # Stop yielding if interrupted
            yield synthesized_chunk
            
        self.is_speaking = False

# This exposes the FastRTC handler to be mounted to FastAPI or used in WebSocket
def get_fastrtc_stream():
    orchestrator = HotelAgentOrchestrator()
    # ReplyOnPause handles VAD and interruption (barge-in) natively
    # We can tune threshold, pre/post speech padding here.
    return Stream(
        modality="audio", 
        handler=ReplyOnPause(
            orchestrator.process,
            input_sample_rate=8000,
            vad_threshold=0.5 # Sensibilité VAD ajustée
        )
    )
