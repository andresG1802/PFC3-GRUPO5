def fix_tokenizer(tokenizer, new_lang='quz_Latn'):
    """
    Add new language token and mappings for NLLB tokenizer.
    """
    # Requiere NLLB tokenizer; si no existe, se intenta suavemente.
    if not hasattr(tokenizer, 'additional_special_tokens'):
        try:
            tokenizer.add_special_tokens({'additional_special_tokens': [new_lang]})
        except Exception:
            pass
    else:
        if new_lang not in tokenizer.additional_special_tokens:
            tokenizer.add_special_tokens({'additional_special_tokens': [new_lang]})

    if not hasattr(tokenizer, 'lang_code_to_id'):
        tokenizer.lang_code_to_id = {}

    try:
        new_lang_id = tokenizer.convert_tokens_to_ids(new_lang)
        tokenizer.lang_code_to_id.setdefault(new_lang, new_lang_id)
    except Exception:
        # si no existe el token, ya se añadió con add_special_tokens y convert dará un id distinto
        pass

    if not hasattr(tokenizer, 'id_to_lang_code'):
        tokenizer.id_to_lang_code = {}
    try:
        tokenizer.id_to_lang_code[tokenizer.lang_code_to_id[new_lang]] = new_lang
    except Exception:
        pass

    return tokenizer
