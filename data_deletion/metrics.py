def get_accuracy(model,
                 tokenizer,
                 batches,
                 network=None,
                 N=None,
                 verbose=False):

    # get token idxs for A, B, C, D
    A_idx = tokenizer.encode("A")[-1]
    B_idx = tokenizer.encode("B")[-1]
    C_idx = tokenizer.encode("C")[-1]
    D_idx = tokenizer.encode("D")[-1]
    choice_idxs = t.tensor([A_idx, B_idx, C_idx, D_idx]).to(model.device)

    corrects = []
    for i, batch in tqdm(enumerate(batches)):
        if N is not None and i > N:
            break
        if i % 10 == 0 and i > 0 and verbose:
            print(f"{i}/ {N}; {len(corrects)}", end='\r')
        texts = [x[0] for x in batch]
        answers = t.tensor([x[1] for x in batch]).to(model.device)
        inputs = tokenizer(texts, return_tensors="pt",
                           padding=True).to(model.device)
        with torch.no_grad():
            if network is None:
                outputs = model(**inputs).logits[:, -1, choice_idxs]
            else:
                with network:
                    outputs = model(**inputs).logits[:, -1, choice_idxs]
        predictions = outputs.argmax(dim=-1)
        corrects.extend((predictions == answers).tolist())

        if verbose:
            print(f"predictions: {predictions}")
            print(f"corrects: {corrects}")
    return corrects

