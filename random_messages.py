# response_handler.py
import random

class Random_messages:
    def __init__(self, file_path="single_lines.txt"):
        self.file_path = file_path
        self.responses = self.load_responses()
    
    def load_responses(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as file:
                # Read lines and remove empty lines and whitespace
                responses = [line.strip() for line in file if line.strip()]
            return responses
        except FileNotFoundError:
            print(f"Warning: Response file {self.file_path} not found. Using default responses.")
            return ["You're not authorized, spedass!"]
    
    def get_random_response(self):
        """Return a formatted random response with prefix and suffix"""
        base_response = random.choice(self.responses) if self.responses else "You're not authorized, spedass!"
        formatted_response = f"Uh Oh!! not authorize😭🥸\n{base_response}\nNice try tho.🤡🤡"
        return formatted_response

# Create a single instance to be imported
response_handler = Random_messages()