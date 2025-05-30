# nlp_engine/__init__.py
from .ner_model import GISNamedEntityRecognizer
from .context_parser import GISContextParser
from .model_trainer import GISLanguageModelTrainer

class NLPEngine:
    """Main NLP Engine for GIS commands."""
    
    def __init__(self):
        """Initialize the NLP engine components."""
        self.ner = GISNamedEntityRecognizer()
        self.context_parser = GISContextParser()
        
    def process_command(self, text, active_layers=None, current_crs=None):
        """Process a natural language GIS command.
        
        Args:
            text: The command text
            active_layers: List of currently active layers in QGIS
            current_crs: Current coordinate reference system
            
        Returns:
            Structured interpretation of the GIS command
        """
        # Update context if provided
        if active_layers or current_crs:
            self.context_parser.update_context(active_layers, current_crs)
            
        # First extract entities
        entity_result = self.ner.extract_gis_commands(text)
        
        # Then parse with context
        context_result = self.context_parser.parse_command(text)
        
        # Merge results, preferring entity extraction for specific entities,
        # but using context parsing for overall operation interpretation
        merged_result = {
            "operation": context_result["operation"],
            "input_layer": entity_result["primary_target"] or context_result.get("input_layer"),
            "parameters": {**context_result.get("parameters", {}), **entity_result.get("parameters", {})},
            "spatial_relationship": context_result.get("spatial_relationship"),
            "confidence": entity_result.get("confidence", 0.5),
            "original_text": text
        }
        
        return merged_result