# nlp_engine/ner_model.py
import spacy
from spacy.tokens import Doc, Span
from spacy.training import Example
import torch
from typing import List, Dict, Any, Optional, Tuple
import os
import json

class GISNamedEntityRecognizer:
    """Custom Named Entity Recognition model for GIS-specific terminology."""
    
    # GIS-specific entity types beyond standard spaCy entities
    GIS_ENTITY_TYPES = [
        "GIS_LAYER", "GIS_TOOL", "SPATIAL_RELATION", "COORDINATE", 
        "DISTANCE", "LOCATION", "FEATURE_TYPE", "ATTRIBUTE"
    ]
    
    def __init__(self, model_path: Optional[str] = None):
        """Initialize the NER model.
        
        Args:
            model_path: Path to a pre-trained model, or None to use a base model
        """
        # Initialize with base model if no specific model is provided
        if model_path and os.path.exists(model_path):
            self.nlp = spacy.load(model_path)
            print(f"Loaded custom GIS NER model from {model_path}")
        else:
            # Start with a base model and customize
            self.nlp = spacy.load("en_core_web_sm")
            print("Using base spaCy model with GIS customizations")
            
            # Add custom entity types to the NER pipe
            if "ner" not in self.nlp.pipe_names:
                ner = self.nlp.add_pipe("ner")
            else:
                ner = self.nlp.get_pipe("ner")
                
            # Add GIS-specific entity labels
            for entity_type in self.GIS_ENTITY_TYPES:
                ner.add_label(entity_type)
    
    def train(self, training_data: List[Tuple[str, Dict[str, Any]]], epochs: int = 30):
        """Fine-tune the NER model with GIS-specific training data.
        
        Args:
            training_data: List of (text, annotations) pairs
            epochs: Number of training iterations
        """
        # Convert training data to spaCy format
        examples = []
        for text, annotations in training_data:
            doc = self.nlp.make_doc(text)
            example = Example.from_dict(doc, annotations)
            examples.append(example)
        
        # Only train the NER component
        ner = self.nlp.get_pipe("ner")
        
        # Train with dropout to prevent overfitting
        dropout = 0.2
        
        # Other pipes will be disabled during training to focus only on NER
        other_pipes = [pipe for pipe in self.nlp.pipe_names if pipe != "ner"]
        
        with self.nlp.disable_pipes(*other_pipes):
            optimizer = self.nlp.create_optimizer()
            
            print("Training GIS-specific NER model...")
            for epoch in range(epochs):
                losses = {}
                batches = spacy.util.minibatch(examples, size=8)
                
                for batch in batches:
                    self.nlp.update(batch, drop=dropout, losses=losses, sgd=optimizer)
                
                print(f"Epoch {epoch+1}/{epochs}, Loss: {losses['ner']:.4f}")
    
    def save(self, output_path: str):
        """Save the trained model to disk.
        
        Args:
            output_path: Directory to save the model
        """
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        
        self.nlp.to_disk(output_path)
        print(f"Model saved to {output_path}")
    
    def annotate_text(self, text: str) -> Dict[str, Any]:
        """Process text and extract GIS-specific entities.
        
        Args:
            text: Input text containing GIS commands or queries
            
        Returns:
            Dictionary containing recognized entities and their types
        """
        doc = self.nlp(text)
        
        entities = []
        for ent in doc.ents:
            entities.append({
                "text": ent.text,
                "start": ent.start_char,
                "end": ent.end_char,
                "type": ent.label_
            })
        
        # Extract additional GIS-relevant information
        result = {
            "entities": entities,
            "tokens": [token.text for token in doc],
            "pos_tags": [token.pos_ for token in doc],
            "dependencies": [(token.text, token.dep_, token.head.text) for token in doc]
        }
        
        return result
    
    def extract_gis_commands(self, text: str) -> Dict[str, Any]:
        """Extracts GIS operations, parameters, and targets from text.
        
        Args:
            text: Natural language GIS command
            
        Returns:
            Structured representation of the GIS command
        """
        doc = self.nlp(text)
        
        # Initialize extraction results
        result = {
            "action": None,          # The GIS operation (buffer, clip, etc.)
            "primary_target": None,  # The main layer or data to operate on
            "parameters": {},        # Operation parameters (distance, etc.)
            "output": None,          # Desired output name/format
            "spatial_modifiers": [], # Spatial relationships (near, intersects)
            "confidence": 0.0,       # Confidence in the extraction
        }
        
        # Extract action verbs (potential GIS operations)
        action_verbs = [token.lemma_ for token in doc if token.pos_ == "VERB"]
        
        # Extract potential targets (nouns that might be layers)
        potential_targets = [token.text for token in doc if token.pos_ in ["NOUN", "PROPN"]]
        
        # Look for entities that might be parameters
        for ent in doc.ents:
            if ent.label_ == "CARDINAL" or ent.label_ == "QUANTITY":
                # Could be a distance parameter
                result["parameters"]["distance"] = ent.text
            elif ent.label_ == "DISTANCE":
                result["parameters"]["distance"] = ent.text
            elif ent.label_ == "GIS_LAYER":
                # Could be a target layer
                if not result["primary_target"]:
                    result["primary_target"] = ent.text
            
        # Simple heuristic assignment if we detected entities
        if action_verbs and not result["action"]:
            result["action"] = action_verbs[0]
            
        if potential_targets and not result["primary_target"]:
            result["primary_target"] = potential_targets[0]
        
        # Set a base confidence - this would be refined in a real implementation
        result["confidence"] = 0.7 if result["action"] and result["primary_target"] else 0.3
            
        return result
    
    def generate_training_data(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Generate synthetic training data for GIS-specific NER.
        
        Returns:
            List of (text, annotations) pairs suitable for training
        """
        # This is a simplified example - a real implementation would have
        # much more comprehensive training data
        training_data = []
        
        # Example 1: Buffer operation
        text = "Create a 500 meter buffer around the rivers layer"
        annotations = {
            "entities": [
                (8, 18, "DISTANCE"),      # "500 meter"
                (36, 42, "GIS_LAYER"),    # "rivers"
            ]
        }
        training_data.append((text, annotations))
        
        # Example 2: Intersection
        text = "Find all buildings that intersect with the flood zone"
        annotations = {
            "entities": [
                (10, 19, "GIS_LAYER"),    # "buildings"
                (40, 50, "GIS_LAYER"),    # "flood zone"
            ]
        }
        training_data.append((text, annotations))
        
        # Example 3: Select by attribute
        text = "Select roads where type equals highway and condition is good"
        annotations = {
            "entities": [
                (7, 12, "GIS_LAYER"),      # "roads"
                (19, 23, "ATTRIBUTE"),     # "type"
                (32, 39, "FEATURE_TYPE"),  # "highway"
                (44, 53, "ATTRIBUTE"),     # "condition"
            ]
        }
        training_data.append((text, annotations))
        
        # Many more examples would be needed in practice
        
        return training_data