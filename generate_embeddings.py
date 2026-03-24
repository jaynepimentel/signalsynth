#!/usr/bin/env python3
"""
Generate embeddings for semantic search.
"""

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import numpy as np
import json
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

def generate_embeddings():
    """Generate embeddings for all insights."""
    
    print("🔄 Loading embedding model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    print("📚 Loading insights...")
    with open('precomputed_insights.json', 'r', encoding='utf-8') as f:
        insights = json.load(f)
    
    print(f"📝 Preparing text for {len(insights)} insights...")
    texts = []
    for insight in insights:
        # Combine relevant text fields for embedding
        text_parts = []
        if insight.get('text'):
            text_parts.append(insight['text'])
        if insight.get('title'):
            text_parts.append(insight['title'])
        if insight.get('type_tag'):
            text_parts.append(insight['type_tag'])
        if insight.get('subtag'):
            text_parts.append(insight['subtag'])
        if insight.get('theme'):
            text_parts.append(insight['theme'])
        # Add source and persona for context
        if insight.get('source'):
            text_parts.append(f"Source: {insight['source']}")
        if insight.get('persona'):
            text_parts.append(f"Persona: {insight['persona']}")
        
        combined_text = ' '.join(text_parts)
        texts.append(combined_text)
    
    print("🧠 Generating embeddings...")
    batch_size = 32
    embeddings = []
    
    for i in tqdm(range(0, len(texts), batch_size), desc="Processing batches"):
        batch_texts = texts[i:i+batch_size]
        batch_embeddings = model.encode(
            batch_texts, 
            convert_to_numpy=True,
            show_progress_bar=False
        )
        embeddings.append(batch_embeddings)
    
    # Concatenate all batches
    all_embeddings = np.vstack(embeddings)
    
    print(f"💾 Saving {all_embeddings.shape} embeddings...")
    np.save('precomputed_embeddings.npy', all_embeddings)
    
    print("✅ Embeddings generated and saved successfully!")
    print(f"📊 Shape: {all_embeddings.shape}")
    print(f"📏 Dimension: {all_embeddings.shape[1]}")
    
    # Test loading
    print("🔍 Verifying saved embeddings...")
    test_embeddings = np.load('precomputed_embeddings.npy')
    assert test_embeddings.shape == all_embeddings.shape, "Shape mismatch!"
    print("✅ Verification passed!")

if __name__ == "__main__":
    generate_embeddings()
