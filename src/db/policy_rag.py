import logging

logger = logging.getLogger(__name__)


class PolicyRAG:
    """
    Superlinked integration for hotel policies (pets, check-in times, etc.)
    Mocked KB for demo.
    """

    def __init__(self):
        self.kb = [
            "L'arrivee (check-in) est a 15h00 et le depart (check-out) est a 11h00.",
            "Les animaux sont acceptes avec un supplement de 50 euros par sejour.",
            "Le petit-dejeuner est servi de 7h00 a 10h00 dans le lobby.",
            "Les annulations sont remboursables a 100% si elles sont faites au moins 24h a l'avance.",
        ]

    def query(self, question: str) -> str:
        logger.info(f"Querying Superlinked RAG for: {question}")
        q = question.lower()

        if any(k in q for k in ["pet", "dog", "cat", "animal", "chien", "chat", "animaux"]):
            return self.kb[1]
        if any(k in q for k in ["breakfast", "food", "petit", "dejeuner", "d?jeuner", "repas"]):
            return self.kb[2]
        if any(k in q for k in ["cancel", "refund", "annulation", "remboursement"]):
            return self.kb[3]
        if any(k in q for k in ["time", "horaire", "heure", "check-in", "check-out", "arrivee", "arriv?e", "depart", "d?part"]):
            return self.kb[0]

        return (
            "Je n'ai pas encore cette information exacte dans la base de politiques. "
            "Souhaitez-vous que je vous mette en relation avec la reception ?"
        )


rag = PolicyRAG()
