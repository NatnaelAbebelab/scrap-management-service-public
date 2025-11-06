import re

def parse_scrap_grade(text):
    grade = {"H": 0, "M": 0, "L": 0}
    
    # Normalize input
    text = text.lower()
    
    # If it contains percentages
    if "%" in text:
        matches = re.findall(r'(\d+)%([hml])', text)
        for percent, label in matches:
            grade[label.upper()] = int(percent)
    else:
        # Look for exact words
        if "heavy" in text:
            grade["H"] = 100
        elif "medium" in text:
            grade["M"] = 100
        elif "light" in text:
            grade["L"] = 100

    return grade
