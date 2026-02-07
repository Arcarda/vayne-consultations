import csv
import sys
import time
import os
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv
from colorama import init, Fore, Style
import prompts

# Initialize Colorama
init(autoreset=True)

# Load Env
load_dotenv()

def get_llm_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print(f"{Fore.RED}[!] Error: OPENAI_API_KEY not found in environment.{Style.RESET_ALL}")
        return None
    return OpenAI(api_key=api_key)

def hard_check(url):
    """
    Performs technical checks: Status Code, Response Time.
    """
    try:
        if not url.startswith("http"):
            url = f"https://{url}"
        
        start_time = time.time()
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (VayneConsulting Scout)"})
        elapsed = time.time() - start_time
        
        return {
            "status": response.status_code,
            "response_time_sec": round(elapsed, 2),
            "valid": response.status_code == 200,
            "html": response.text,
            "final_url": response.url
        }
    except Exception as e:
        return {
            "error": str(e),
            "valid": False
        }

def soft_check(html_content, client):
    """
    Extracts Hero Section text and uses LLM to generate an insight.
    """
    if not client:
        return "LLM Analysis Skipped (No Key)"

    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Heuristic to find Hero Content: First H1, H2, and first Paragraph
    hero_text = []
    
    h1 = soup.find('h1')
    if h1: hero_text.append(f"H1: {h1.get_text(strip=True)}")
    
    h2 = soup.find('h2')
    if h2: hero_text.append(f"H2: {h2.get_text(strip=True)}")
    
    p = soup.find('p')
    if p: hero_text.append(f"P: {p.get_text(strip=True)[:200]}...") # truncate
    
    if not hero_text:
        # Fallback: First 500 chars of body
        body = soup.find('body')
        if body:
            text = body.get_text(strip=True)[:500]
            hero_text.append(f"Body: {text}")
        else:
            return "Could not extract content."

    content_blob = "\n".join(hero_text)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o", # Or gpt-3.5-turbo if cost is concern
            messages=[
                {"role": "system", "content": prompts.ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": f"Analyze this hero section content:\n\n{content_blob}"}
            ],
            temperature=0.7,
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"LLM Error: {str(e)}"

def run_scout(input_csv):
    client = get_llm_client()
    results = []

    print(f"{Fore.CYAN}[*] Starting Smart Scout on {input_csv}...{Style.RESET_ALL}")

    try:
        with open(input_csv, 'r') as f:
            reader = csv.reader(f)
            targets = [row[0] for row in reader if row]
    except FileNotFoundError:
        print(f"{Fore.RED}[!] Error: File {input_csv} not found.{Style.RESET_ALL}")
        return

    for target in targets:
        print(f"\n{Fore.YELLOW}[>] Scouting: {target}{Style.RESET_ALL}")
        
        # 1. Hard Check
        tech_data = hard_check(target)
        
        if not tech_data['valid']:
            print(f"{Fore.RED}    [x] Failed: {tech_data.get('error') or tech_data.get('status')}{Style.RESET_ALL}")
            results.append({"url": target, "status": "FAILED", "note": tech_data.get('error')})
            continue

        print(f"{Fore.GREEN}    [+] Online ({tech_data['response_time_sec']}s){Style.RESET_ALL}")

        # 2. Soft Check
        print(f"    {Fore.BLUE}[~] Analyzing Content...{Style.RESET_ALL}")
        insight = soft_check(tech_data['html'], client)
        
        # 3. Draft Email
        email_draft = prompts.EMAIL_TEMPLATE.format(
            domain=target,
            insight=insight
        )

        results.append({
            "url": target,
            "load_time": tech_data['response_time_sec'],
            "insight": insight,
            "email_draft": email_draft
        })
        
        print(f"{Fore.MAGENTA}    [i] Insight: {insight}{Style.RESET_ALL}")

    # Save Results
    # For now, just dumping to a simple text report or JSON could be better, but let's stick to console/simple file for prototype
    import json
    with open('audit_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n{Fore.CYAN}[*] Scout Run Complete. Results saved to audit_results.json{Style.RESET_ALL}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scout.py <targets.csv>")
        sys.exit(1)
    
    run_scout(sys.argv[1])
