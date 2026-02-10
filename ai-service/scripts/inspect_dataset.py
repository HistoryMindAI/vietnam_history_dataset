from datasets import load_dataset

ds = load_dataset("minhxthanh/Vietnam-History-1M-Vi", split="train", streaming=True)
print("First row:", next(iter(ds)))
