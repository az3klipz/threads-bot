import random
import re
import datetime

class SpintaxParser:
    @staticmethod
    def parse(text):
        """
        Parses spintax in the format {option1|option2|{nested1|nested2}}
        """
        if not text:
            return ""
            
        # Recursive function to handle nested spintax
        def spin(match):
            options = match.group(1).split('|')
            return SpintaxParser.parse(random.choice(options))
            
        # Regex to find the innermost spintax { ... }
        # This pattern finds {content} where content has no { or } inside
        pattern = r'\{([^{}]+)\}'
        
        while True:
            new_text = re.sub(pattern, spin, text)
            if new_text == text:
                break
            text = new_text
            
        return text

    @staticmethod
    def process_comment(template, username="friend"):
        """
        Process a comment template with spintax and variables
        Variables: <username>, <day>
        """
        # 1. Parse Spintax
        text = SpintaxParser.parse(template)
        
        # 2. Replace Variables
        # Handle <username> - remove @ if it's already in the username passed
        clean_username = username.replace("@", "")
        text = text.replace("<username>", f"@{clean_username}")
        
        # Day of week
        today = datetime.datetime.now().strftime("%A")
        text = text.replace("<day>", today)
        
        return text
