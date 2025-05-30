# nlp_engine/model_trainer.py
import os
import json
from typing import List, Dict, Any, Optional
import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification, TrainingArguments, Trainer
import numpy as np
from datasets import Dataset

class GISLanguageModelTrainer:
    """Fine-tuning framework for language models specifically for GIS terminology."""
    
    def __init__(self, model_name: str = "distilbert-base-uncased"):
        """Initialize the trainer.
        
        Args:
            model_name: Base model to fine-tune (default: distilbert-base-uncased)
        """
        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = None
        
    def prepare_training_data(self, examples: List[Dict[str, Any]]) -> Dataset:
        """Convert training examples to HuggingFace dataset format.
        
        Args:
            examples: List of training examples with text and labels
            
        Returns:
            HuggingFace Dataset ready for training
        """
        # Convert examples to features
        features = []
        
        for example in examples:
            text = example["text"]
            
            # Tokenize the input
            tokens = self.tokenizer(
                text,
                padding="max_length",
                truncation=True,
                max_length=128,
                return_tensors="pt"
            )
            
            # Add labels if present (for training)
            if "labels" in example:
                tokens["labels"] = example["labels"]
                
            # Convert to dictionary format
            item = {key: val.squeeze().tolist() for key, val in tokens.items()}
            
            # Add any other fields from the example
            for k, v in example.items():
                if k != "text" and k != "labels":
                    item[k] = v
                    
            features.append(item)
            
        return Dataset.from_list(features)
    
    def load_or_create_model(self, num_labels: int):
        """Load or create a token classification model.
        
        Args:
            num_labels: Number of entity labels to predict
        """
        self.model = AutoModelForTokenClassification.from_pretrained(
            self.model_name, 
            num_labels=num_labels
        )
        
    def train(self, train_dataset: Dataset, eval_dataset: Optional[Dataset] = None, 
              output_dir: str = "./gis_model", num_train_epochs: int = 3):
        """Fine-tune the model on GIS-specific data.
        
        Args:
            train_dataset: Dataset for training
            eval_dataset: Optional dataset for evaluation
            output_dir: Directory to save the model
            num_train_epochs: Number of training epochs
        """
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=num_train_epochs,
            per_device_train_batch_size=16,
            per_device_eval_batch_size=16,
            warmup_steps=500,
            weight_decay=0.01,
            logging_dir=f"{output_dir}/logs",
            logging_steps=10,
            evaluation_strategy="epoch" if eval_dataset else "no",
            save_strategy="epoch",
            load_best_model_at_end=True if eval_dataset else False,
        )
        
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
        )
        
        trainer.train()
        
        # Save the final model
        trainer.save_model(output_dir)
        self.tokenizer.save_pretrained(output_dir)
        
    def create_synthetic_training_data(self) -> List[Dict[str, Any]]:
        """Create synthetic training data for GIS NLP training.
        
        Returns:
            List of training examples
        """
        examples = []
        
        # Simple examples of GIS commands
        gis_commands = [
            "Buffer the rivers layer by 500 meters",
            "Select buildings within 1 km of the hospital",
            "Find all roads that intersect with the flood zone",
            "Calculate the area of forest patches",
            "Create a heatmap of crime incidents",
            "Merge all residential zones into one layer",
            "Show elevation above 1000 feet",
            "Extract roads from the OpenStreetMap data",
            "Find the nearest hospital to each school",
            "Count the number of houses in each district"
        ]
        
        # Add more complex examples
        gis_commands.extend([
            "Show me all buildings that are within 500 meters of rivers and have an area greater than 1000 square meters",
            "Calculate the average slope in forested areas that are above 2000 feet elevation",
            "Identify parcels where zoning is commercial and the building footprint covers more than 70% of the lot",
            "Find all roads that need repair and are within city boundaries",
            "Create a 2 kilometer buffer around schools, then select residential areas that fall within these buffers"
        ])
        
        # Convert to training examples (in a real system, these would include proper labels)
        for command in gis_commands:
            examples.append({
                "text": command,
                # In a real implementation, we would have proper token-level labels
                # This is just a placeholder
                "labels": [0] * len(self.tokenizer.encode(command))
            })
            
        return examples