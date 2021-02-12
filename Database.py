import requests


class Database:
    def __init__(self, startTime) -> None:
        self.url = "https://mlstatus.herokuapp.com/database/"
        self.startTime = startTime
        self.generation = 0

    def setOptions(self, options) -> None:
        requests.post(self.url + "setOptions", json={
            "startTime": self.startTime,
            "options": options
        })

    def setGeneration(self, generation) -> None:
        self.generation += generation

    def updateAgentPool(self, id: str, agentPoolData: dict) -> None:
        requests.post(self.url + "updateAgentPool", json={
            "startTime": self.startTime,
            "id": id,
            "agentPoolData": agentPoolData,
            "generation": self.generation
        })

    def storeOutput(self, outputData: dict):
        requests.post(self.url + "storeOutput", json={
            "startTime": self.startTime,
            "outputData": outputData,
            "generation": self.generation
        })