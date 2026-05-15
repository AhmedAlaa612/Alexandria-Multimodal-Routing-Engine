import os
from dotenv import load_dotenv
from agent import AlOstaAgent

def main():
    # 1. Load environment variables from .env file
    load_dotenv()
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    if not GEMINI_API_KEY:
        print("Error: Please specify your GEMINI_API_KEY in the .env file.")
        return
    
    # 2. Create the Agent
    agent = AlOstaAgent(GEMINI_API_KEY)
    
    print("--- Al-Osta is ready to help you! (Type 'exit' or 'quit' to close) ---")
    
    while True:
        # 3. Receive user input
        user_input = input("\nUser: ")
        
        if user_input.lower() in ["خروج", "exit", "quit"]:
            print("Al-Osta: Goodbye! Have a great journey!")
            break
        
        # 4. Process the question and provide the answer
        try:
            answer = agent.process_query(user_input)
            print(f"\nAl-Osta: {answer}")
        except Exception as e:
            print(f"\nAl-Osta: Sorry, I ran into a problem: {e}")

if __name__ == "__main__":
    main()
