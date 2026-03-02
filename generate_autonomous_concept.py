import urllib.request
import json
import time

def generate_prompt_with_ollama(niche, style, model="qwen2.5-coder:14b"):
    """Uses local Ollama to act as the Art Director and output an SDXL prompt."""
    print(f"[{model}] Thinking about: {niche} + {style}...")
    
    url = "http://localhost:11434/api/generate"
    
    system_prompt = (
        "You are a world-class UI/UX art director. Use the user's input to write "
        "a highly detailed, comma-separated Stable Diffusion XL prompt outlining "
        "the exact website hero UI structure, layout, typography, lighting, and textures. "
        "Do NOT include any conversational filler, intro, or outro. ONLY output the comma-separated visual keywords."
    )
    
    user_prompt = f"Design a stunning premium UI homepage mockup for: {niche}. The visual style should be: {style}"
    
    payload = {
        "model": model,
        "system": system_prompt,
        "prompt": user_prompt,
        "stream": False,
        "options": {
            "temperature": 0.7
        }
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), method='POST')
    req.add_header('Content-Type', 'application/json')
    
    try:
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode('utf-8'))
        sdxl_prompt = result.get('response', '').strip()
        print(f"\n[Ollama Output] -> {sdxl_prompt}\n")
        return sdxl_prompt
    except Exception as e:
        print(f"Ollama Error: {e}")
        print("Please ensure Ollama is running.")
        return None

def queue_comfyui_render(positive_prompt, file_prefix):
    """Sends the LLM-generated prompt directly to the ComfyUI rendering backend."""
    print(f"[ComfyUI] Queuing render: {file_prefix}...")
    
    workflow = {
        "10": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "juggernautXL_ragnarokBy.safetensors"
            }
        },
        "11": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": "Detail_Tweaker_XL.safetensors",
                "strength_model": 0.40,
                "strength_clip": 0.40,
                "model": ["10", 0],
                "clip": ["10", 1]
            }
        },
        "20": {
            "class_type": "CLIPTextEncodeSDXL",
            "inputs": {
                "width": 1344,
                "height": 768,
                "crop_w": 0,
                "crop_h": 0,
                "target_width": 1344,
                "target_height": 768,
                "text_g": positive_prompt + ", highly detailed, 4k, professional UI mockup, landing page, web design",
                "text_l": positive_prompt,
                "clip": ["11", 1]
            }
        },
        "21": {
            "class_type": "CLIPTextEncodeSDXL",
            "inputs": {
                "width": 1344,
                "height": 768,
                "crop_w": 0,
                "crop_h": 0,
                "target_width": 1344,
                "target_height": 768,
                "text_g": "blurry, low quality, mobile layout, phone, illustration, cartoon, sketch, nsfw",
                "text_l": "blurry, low quality, mobile, cartoon",
                "clip": ["11", 1]
            }
        },
        "30": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": 1344,
                "height": 768,
                "batch_size": 1
            }
        },
        "40": {
            "class_type": "KSampler",
            "inputs": {
                "seed": int(time.time()),
                "steps": 30,
                "cfg": 7.0,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
                "model": ["11", 0],
                "positive": ["20", 0],
                "negative": ["21", 0],
                "latent_image": ["30", 0]
            }
        },
        "50": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["40", 0],
                "vae": ["10", 2]
            }
        },
        "60": {
            "class_type": "UpscaleModelLoader",
            "inputs": {
                "model_name": "4x-UltraSharp.pth"
            }
        },
        "61": {
            "class_type": "ImageUpscaleWithModel",
            "inputs": {
                "upscale_model": ["60", 0],
                "image": ["50", 0]
            }
        },
        "70": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": file_prefix,
                "images": ["61", 0]
            }
        }
    }
    
    p = {"prompt": workflow}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request("http://127.0.0.1:8188/prompt", data=data)
    
    try:
        urllib.request.urlopen(req)
        print("[ComfyUI] Successfully queued prompt via API. Image will appear in ComfyUI/output.")
    except Exception as e:
        print(f"[ComfyUI] Failed to queue prompt: {e}")

if __name__ == "__main__":
    niche_input = "Elite InfoSec Consulting Firm"
    style_input = "Cyberpunk Neo-Noir, neon red rim lighting, dark glass surfaces, hacker aesthetic, premium luxury UI"
    
    print("--- Starting Autonomous Concept Generation ---")
    
    # 1. Ask Ollama to Brainstorm the Visual Prompt
    # Note: Using qwen2.5-coder:14b or llama3 (must be downloaded locally)
    sdxl_prompt = generate_prompt_with_ollama(niche_input, style_input, model="qwen2.5-coder:14b")
    
    # 2. Feed the Brainstorm to ComfyUI
    if sdxl_prompt:
        queue_comfyui_render(sdxl_prompt, "autonomous_concept_infosec")
    else:
        print("Failed to get prompt from Ollama. Ensure Ollama is running.")
