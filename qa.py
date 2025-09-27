from typing import List
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

class T5Answerer:
    def __init__(self, model_name="google/flan-t5-base"):
        self.tk = AutoTokenizer.from_pretrained(model_name)
        self.m = AutoModelForSeq2SeqLM.from_pretrained(model_name)

    def answer(self, question: str, contexts: List[str], max_new_tokens=200) -> str:
        ctx = "\n\n".join(contexts[:6])
        prompt = (
            "You are a helpful study assistant. Answer concisely using ONLY the context.\n"
            f"Context:\n{ctx}\n\nQuestion: {question}\nAnswer:"
        )
        ids = self.tk(prompt, return_tensors="pt", truncation=True).input_ids
        out = self.m.generate(ids, max_new_tokens=max_new_tokens)
        return self.tk.decode(out[0], skip_special_tokens=True)
