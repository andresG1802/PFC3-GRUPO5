import os
import logging
import torch
from transformers import AutoModelForSeq2SeqLM, NllbTokenizer

from app.utils.tokenizer_fix import fix_tokenizer

MODEL_ID_OR_PATH = os.getenv("MODEL_ID", "pollitoconpapass/QnIA-translation-model")

class Translator:
    def __init__(self, model_id=MODEL_ID_OR_PATH, device=None, use_8bit=False):
        self.model_id = model_id
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.use_8bit = use_8bit
        self._load_model()

    def _load_model(self):
        logging.info(f"Loading model {self.model_id} on device {self.device} (8bit={self.use_8bit})")
        kwargs = {}
        if self.use_8bit:
            # requiere bitsandbytes instalado - opcional
            kwargs.update(dict(load_in_8bit=True, device_map="auto"))
        else:
            kwargs.update(dict(device_map="auto"))

        self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_id, **kwargs)
        self.tokenizer = NllbTokenizer.from_pretrained(self.model_id)
        fix_tokenizer(self.tokenizer, new_lang='quz_Latn')

    def translate(self, text, src_lang="spa_Latn", tgt_lang="quz_Latn", num_beams=4, max_input_length=1024):
        self.tokenizer.src_lang = src_lang
        self.tokenizer.tgt_lang = tgt_lang
        inputs = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=max_input_length)
        inputs = inputs.to(self.model.device)
        out = self.model.generate(
            **inputs,
            forced_bos_token_id=self.tokenizer.convert_tokens_to_ids(tgt_lang),
            num_beams=num_beams
        )
        decoded = self.tokenizer.batch_decode(out, skip_special_tokens=True)
        return decoded[0] if isinstance(decoded, list) else decoded
