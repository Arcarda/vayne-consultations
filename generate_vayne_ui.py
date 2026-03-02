import urllib.request
import json
import io
import time
import os

def queue_prompt(prompt):
    p = {"prompt": prompt}
    data = json.dumps(p).encode('utf-8')
    # Default ComfyUI local server address
    req = urllib.request.Request("http://127.0.0.1:8188/prompt", data=data)
    try:
        urllib.request.urlopen(req)
        print("Successfully queued prompt via API.")
    except Exception as e:
        print(f"Failed to queue prompt: {e}")

# The core API workflow structure based on website_design_workflow.json and standard SDXL parameters
def generate_vayne_concept(positive_prompt, file_prefix):
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
                "text_g": positive_prompt,
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
                "text_g": "blurry, low quality, poorly designed, ugly, amateur, cluttered, bad typography, watermark, logo placeholder, lorem ipsum visible, mobile layout, phone frame, 3D render, photorealistic person, stock photo, illustration, cartoon, sketch, distorted",
                "text_l": "blurry, low quality, mobile, phone, 3D, cartoon, watermark",
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
    
    queue_prompt(workflow)
    # Adding a slight delay so seeds evaluate differently
    time.sleep(1)

# The Prompts for the missing concepts (H, I, J)
concepts = [
    {
        "name": "vayne_prism_h_cybernetic",
        "prompt": "professional UI design mockup for a consulting firm, Vayne Consulting. A futuristic, holographic cybernetic 3D prism made of red data streams floating against a extremely dark pure Vantablack background. Web design, sleek navigation, dark mode, high detail, 4K render, ui/ux"
    },
    {
        "name": "vayne_prism_i_smoke",
        "prompt": "professional UI design mockup for a luxury consulting firm, Vayne Consulting. A moody, atmospheric sharp dark glass prism floating amidst subtle, swirling deep red smoke on a pure black background. Very elegant, mysterious, high-end aesthetic. Dark mode, UI layout, premium."
    },
    {
        "name": "vayne_prism_j_closeup",
        "prompt": "professional UI design mockup for a premium consulting firm. A cinematic, extreme close-up of a dark glass triangular prism. The camera is macro-focused on the sharp edge where a vivid red light beam strikes and bends inside the glass. Pure black background, minimalist UI, sleek typography."
    }
]

print("Sending 3 Vayne concept prompts to ComfyUI...")
for concept in concepts:
    print(f"Queueing: {concept['name']}")
    generate_vayne_concept(concept['prompt'], concept['name'])
    
print("\nAll renders queued! Check your ComfyUI console for generation progress.")
