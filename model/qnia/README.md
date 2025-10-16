---
license: mit
datasets:
- pollitoconpapass/new-cuzco-quechua-translation-dataset
language:
- qu
base_model:
- facebook/nllb-200-distilled-600M
pipeline_tag: translation
---
## Overview
This model is a finetuning of [nllb-200-distilled-600M](https://huggingface.co/facebook/nllb-200-distilled-600M) to handle the Cuzco Quechua language.

## Model Implementation
Use this script to test the model, change the respective values.
```py
import time
from transformers import NllbTokenizer, AutoModelForSeq2SeqLM


def fix_tokenizer(tokenizer, new_lang='quz_Latn'):
    """
    Add a new language token to the tokenizer vocabulary and update language mappings.
    """
    # First ensure we're working with an NLLB tokenizer
    if not hasattr(tokenizer, 'sp_model'):
        raise ValueError("This function expects an NLLB tokenizer")

    # Add the new language token if it's not already present
    if new_lang not in tokenizer.additional_special_tokens:
        tokenizer.add_special_tokens({
            'additional_special_tokens': [new_lang]
        })
    
    # Initialize lang_code_to_id if it doesn't exist
    if not hasattr(tokenizer, 'lang_code_to_id'):
        tokenizer.lang_code_to_id = {}
        
    # Add the new language to lang_code_to_id mapping
    if new_lang not in tokenizer.lang_code_to_id:
        # Get the ID for the new language token
        new_lang_id = tokenizer.convert_tokens_to_ids(new_lang)
        tokenizer.lang_code_to_id[new_lang] = new_lang_id
        
    # Initialize id_to_lang_code if it doesn't exist
    if not hasattr(tokenizer, 'id_to_lang_code'):
        tokenizer.id_to_lang_code = {}
        
    # Update the reverse mapping
    tokenizer.id_to_lang_code[tokenizer.lang_code_to_id[new_lang]] = new_lang

    return tokenizer


MODEL_URL = "pollitoconpapass/QnIA-translation-model"
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_URL)
tokenizer = NllbTokenizer.from_pretrained(MODEL_URL)
fix_tokenizer(tokenizer)

def translate(text, src_lang='spa_Latn', tgt_lang='quz_Latn', a=32, b=3, max_input_length=1024, num_beams=4, **kwargs):
    tokenizer.src_lang = src_lang
    tokenizer.tgt_lang = tgt_lang
    inputs = tokenizer(text, return_tensors='pt', padding=True, truncation=True, max_length=max_input_length)
    result = model.generate(
        **inputs.to(model.device),
        forced_bos_token_id=tokenizer.convert_tokens_to_ids(tgt_lang),
        max_new_tokens=int(a + b * inputs.input_ids.shape[1]),
        num_beams=num_beams,
        **kwargs
    )
    return tokenizer.batch_decode(result, skip_special_tokens=True)


def translate_v2(text, model, tokenizer, src_lang='spa_Latn', tgt_lang='quz_Latn',
                max_length='auto', num_beams=4, no_repeat_ngram_size=4, n_out=None, **kwargs):
    
    tokenizer.src_lang = src_lang
    encoded = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    if max_length == 'auto':
        max_length = int(32 + 2.0 * encoded.input_ids.shape[1])
    model.eval()
    generated_tokens = model.generate(
        **encoded.to(model.device),
        forced_bos_token_id=tokenizer.lang_code_to_id[tgt_lang],
        max_length=max_length,
        num_beams=num_beams,
        no_repeat_ngram_size=no_repeat_ngram_size,
        num_return_sequences=n_out or 1,
        **kwargs
    )
    out = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)
    if isinstance(text, str) and n_out is None:
        return out[0]
    return out


# === MAIN ===
t = '''
Subes centelleante de labios y de ojeras!
Por tus venas subo, como un can herido
que busca el refugio de blandas aceras.

Amor, en el mundo tú eres un pecado!
Mi beso en la punta chispeante del cuerno
del diablo; mi beso que es credo sagrado!
'''

start = time.time()
result_v1 = translate(t, 'spa_Latn', 'quz_Latn')
print(f"\n{result_v1}")

end = time.time()
print(f"\nTime for method v1: {end - start}")


# start_v2 = time.time()
# result_v2 = translate_v2(t, model, tokenizer)
# print(result_v2)

# end_v2 = time.time()
# print(f"\nTime for method v1: {end_v2 - start_v2}")
```
