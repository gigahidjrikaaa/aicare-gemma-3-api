import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer

# 1. Configuration
model_id = "meta-llama/Meta-Llama-3-8B" # The base model you want to fine-tune
dataset_path = "./example-dataset.json"          # Your local dataset file
output_dir = "./llama3-8b-finetuned-adapters" # Where to save the trained LoRA adapters

# 2. Load the Dataset
dataset = load_dataset("json", data_files=dataset_path, split="train")

# 3. Model and Tokenizer Loading with Quantization
# Configure 4-bit quantization to fit the model on your GPU
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16
)

tokenizer = AutoTokenizer.from_pretrained(model_id)
# Important: Add a padding token if the base model doesn't have one
if tokenizer.pad_token is None:
    tokenizer.add_special_tokens({'pad_token': '[PAD]'})

model = AutoModelForCausalLM.from_pretrained(
    model_id,
    quantization_config=bnb_config,
    device_map="auto" # Let accelerate handle GPU placement
)

# 4. PEFT (LoRA) Configuration
# Prepare the model for k-bit training
model = prepare_model_for_kbit_training(model)

# Define the LoRA configuration
lora_config = LoraConfig(
    r=16, # Rank of the update matrices. Higher rank means more parameters to train.
    lora_alpha=32, # LoRA scaling factor.
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"], # Apply LoRA to attention layers
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"
)

# Wrap the model with PEFT
model = get_peft_model(model, lora_config)

# 5. Training Arguments
training_args = TrainingArguments(
    output_dir=output_dir,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    num_train_epochs=3,
    logging_steps=10,
    save_strategy="epoch",
    fp16=True, # Use fp16 for training
)

# 6. Initialize the Trainer
trainer = SFTTrainer(
    model=model,
    train_dataset=dataset,
    peft_config=lora_config,
    dataset_text_field="output", # Assuming the 'output' field contains the text to learn
    max_seq_length=1024,
    tokenizer=tokenizer,
    args=training_args,
)

# 7. Start Training!
trainer.train()

# 8. Save the final adapters
trainer.save_model(output_dir)
print(f"LoRA adapters saved to {output_dir}")
