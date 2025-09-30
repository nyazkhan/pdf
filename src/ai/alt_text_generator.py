import logging
from typing import Optional
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import warnings

# Suppress some transformer warnings
warnings.filterwarnings("ignore", category=UserWarning, module="transformers")

logger = logging.getLogger(__name__)


class AltTextGenerator:
    def __init__(self, model_name: str = "Salesforce/blip-image-captioning-base", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self.processor = None
        self.model = None
        self.loaded = False
        
        self.load_model()
    
    def load_model(self):
        try:
            logger.info(f"Loading BLIP model: {self.model_name}")
            
            # Load processor and model
            self.processor = BlipProcessor.from_pretrained(self.model_name)
            self.model = BlipForConditionalGeneration.from_pretrained(self.model_name)
            
            # Move to specified device
            if self.device == "cuda" and torch.cuda.is_available():
                self.model = self.model.to("cuda")
                logger.info("Model loaded on CUDA")
            else:
                self.device = "cpu"
                self.model = self.model.to("cpu")
                logger.info("Model loaded on CPU")
            
            self.loaded = True
            logger.info("BLIP model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load BLIP model: {e}")
            self.loaded = False
            raise
    
    def is_available(self) -> bool:
        return self.loaded and self.processor is not None and self.model is not None
    
    def generate_caption(self, image: Image.Image, context: str = "") -> str:
        if not self.is_available():
            raise RuntimeError("Model not available")
        
        try:
            # Ensure image is in RGB mode
            if image.mode != "RGB":
                image = image.convert("RGB")
            
            # Prepare inputs
            if context:
                # Use conditional generation with context
                inputs = self.processor(image, context, return_tensors="pt")
            else:
                # Unconditional generation
                inputs = self.processor(image, return_tensors="pt")
            
            # Move inputs to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Generate caption
            with torch.no_grad():
                if context:
                    # For conditional captioning
                    outputs = self.model.generate(
                        **inputs,
                        max_new_tokens=50,
                        min_length=10,
                        num_beams=4,
                        early_stopping=True,
                        do_sample=False,
                        temperature=1.0
                    )
                else:
                    # For unconditional captioning  
                    outputs = self.model.generate(
                        **inputs,
                        max_new_tokens=50,
                        min_length=10,
                        num_beams=4,
                        early_stopping=True,
                        do_sample=False
                    )
            
            # Decode the generated caption
            caption = self.processor.decode(outputs[0], skip_special_tokens=True)
            
            # Clean up the caption
            caption = self.clean_caption(caption)
            
            return caption
            
        except Exception as e:
            logger.error(f"Failed to generate caption: {e}")
            raise
    
    def clean_caption(self, caption: str) -> str:
        """Clean and improve the generated caption"""
        # Remove common artifacts
        caption = caption.strip()
        
        # Remove "a picture of", "an image of" etc. if at the beginning
        prefixes_to_remove = [
            "a picture of ",
            "an image of ",
            "a photo of ",
            "the image shows ",
            "this image shows ",
            "there is ",
            "there are "
        ]
        
        caption_lower = caption.lower()
        for prefix in prefixes_to_remove:
            if caption_lower.startswith(prefix):
                caption = caption[len(prefix):]
                break
        
        # Capitalize first letter
        if caption:
            caption = caption[0].upper() + caption[1:]
        
        # Ensure it ends with a period
        if caption and not caption.endswith(('.', '!', '?')):
            caption += '.'
        
        return caption
    
    def generate_batch_captions(self, images: list, contexts: list = None) -> list:
        """Generate captions for multiple images"""
        if not self.is_available():
            raise RuntimeError("Model not available")
        
        captions = []
        contexts = contexts or [""] * len(images)
        
        for i, image in enumerate(images):
            try:
                context = contexts[i] if i < len(contexts) else ""
                caption = self.generate_caption(image, context)
                captions.append(caption)
            except Exception as e:
                logger.error(f"Failed to generate caption for image {i}: {e}")
                captions.append(f"Error generating caption: {str(e)}")
        
        return captions
    
    def generate_accessible_description(self, image: Image.Image, context: str = "") -> str:
        """Generate a more detailed accessible description"""
        try:
            # First get the basic caption
            basic_caption = self.generate_caption(image, context)
            
            # For accessibility, we want more descriptive text
            # This could be enhanced with additional models or rules
            
            # Add context if provided
            if context.strip():
                accessible_desc = f"In the context of {context.strip()}: {basic_caption}"
            else:
                accessible_desc = basic_caption
            
            # Ensure it's descriptive enough
            if len(accessible_desc.split()) < 5:
                accessible_desc = f"Image showing {accessible_desc}"
            
            return accessible_desc
            
        except Exception as e:
            logger.error(f"Failed to generate accessible description: {e}")
            return self.generate_caption(image, context)
    
    def analyze_image_type(self, image: Image.Image) -> str:
        """Analyze what type of image this might be (chart, diagram, photo, etc.)"""
        try:
            # This is a simplified analysis
            # Could be enhanced with specialized models
            
            width, height = image.size
            aspect_ratio = width / height
            
            # Get basic caption to analyze content
            caption = self.generate_caption(image)
            caption_lower = caption.lower()
            
            # Simple classification based on caption content
            if any(word in caption_lower for word in ["chart", "graph", "plot", "diagram"]):
                return "chart"
            elif any(word in caption_lower for word in ["table", "spreadsheet", "data"]):
                return "table"  
            elif any(word in caption_lower for word in ["text", "document", "page", "writing"]):
                return "text"
            elif any(word in caption_lower for word in ["logo", "sign", "symbol"]):
                return "logo"
            elif any(word in caption_lower for word in ["person", "people", "man", "woman", "child"]):
                return "photo"
            else:
                return "image"
                
        except Exception as e:
            logger.error(f"Failed to analyze image type: {e}")
            return "image"
    
    def get_model_info(self) -> dict:
        """Get information about the loaded model"""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "loaded": self.loaded,
            "available": self.is_available(),
            "cuda_available": torch.cuda.is_available() if torch else False
        }