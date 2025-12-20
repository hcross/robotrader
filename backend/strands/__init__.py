"""
Strands Framework (Local Implementation)
"""

class Agent:
    def __init__(self, name, role):
        self.name = name
        self.role = role
        self.mailbox = []

    def receive_message(self, message):
        self.mailbox.append(message)
        print(f"[{self.name}] Received: {message}")

    def send_message(self, recipient, message):
        print(f"[{self.name}] Sending to {recipient.name}: {message}")
        recipient.receive_message(message)

    def run(self):
        raise NotImplementedError("Agents must implement run()")
