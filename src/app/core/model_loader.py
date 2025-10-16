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
        """
        Carga el modelo sin usar device_map ni offload; evita pasar map_location a from_pretrained.
        """
        logging.info(f"Loading model {self.model_id} (attempt device: {self.device}, use_8bit={self.use_8bit})")

        if self.use_8bit:
            raise RuntimeError("8-bit loading requested. Use bitsandbytes+accelerate in Linux/Docker.")

        try:
            # determinar dispositivo objetivo
            use_cuda = torch.cuda.is_available()
            target_device = torch.device("cuda" if use_cuda else "cpu")
            logging.info(f"Target device: {target_device}")

            # Cargar modelo (no pasar map_location aquí)
            # low_cpu_mem_usage ayuda a reducir memoria temporal durante la carga
            self.model = AutoModelForSeq2SeqLM.from_pretrained(
                self.model_id,
                low_cpu_mem_usage=True,
            )

            # mover explícitamente a target_device
            try:
                self.model.to(target_device)
            except Exception:
                logging.exception("No se pudo mover el modelo al dispositivo; seguirá donde esté.")

            # cargar tokenizer y aplicar fix
            self.tokenizer = NllbTokenizer.from_pretrained(self.model_id)
            fix_tokenizer(self.tokenizer, new_lang='quz_Latn')

            logging.info("Modelo y tokenizer cargados correctamente.")

        except Exception as e:
            logging.exception("Error cargando el modelo:")
            raise

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
