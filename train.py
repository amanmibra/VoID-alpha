from datetime import datetime
from tqdm import tqdm
import wandb

# torch
import torch
import torchaudio
from torch import nn
from torch.utils.data import DataLoader

# internal
from dataset import VoiceDataset
from cnn import CNNetwork

BATCH_SIZE = 128
EPOCHS = 10
LEARNING_RATE = 0.001

TRAIN_FILE="data/train"
AISF_TRAIN_FILE="data/aisf/train"
TEST_FILE="data/test"
SAMPLE_RATE=48000

def train(model, train_dataloader, loss_fn, optimizer, device, epochs, test_dataloader=None):
    training_acc = []
    training_loss = []
    testing_acc = []
    testing_loss = []

    for i in range(epochs):
        print(f"Epoch {i + 1}/{epochs}")

        # train model
        train_epoch_loss, train_epoch_acc = train_epoch(model, train_dataloader, loss_fn, optimizer, device)

        # training metrics
        training_loss.append(train_epoch_loss/len(train_dataloader))
        training_acc.append(train_epoch_acc/len(train_dataloader))

        print("Training Loss: {:.2f}, Training Accuracy  {}".format(training_loss[i], training_acc[i]))
        wandb.log({'training_loss': training_loss[i], 'training_acc': training_acc[i]})

        if test_dataloader:
            # test model
            test_epoch_loss, test_epoch_acc = validate_epoch(model, test_dataloader, loss_fn, device)
            
            # testing metrics
            testing_loss.append(test_epoch_loss/len(test_dataloader))
            testing_acc.append(test_epoch_acc/len(test_dataloader))

            print("Testing Loss: {:.2f}, Testing Accuracy  {}".format(testing_loss[i], testing_acc[i]))
            wandb.log({'testing_loss': testing_loss[i], 'testing_acc': testing_acc[i]})

        print ("-------------------------------------------- \n")
    
    print("---- Finished Training ----")
    return training_acc, training_loss, testing_acc, testing_loss
  

def train_epoch(model, train_dataloader, loss_fn, optimizer, device):
    train_loss = 0.0
    train_acc = 0.0
    total = 0.0

    model.train()

    for wav, target in tqdm(train_dataloader, "Training batch..."):
        wav, target = wav.to(device), target.to(device)

        # calculate loss
        output = model(wav)
        loss = loss_fn(output, target)

        # backprop and update weights
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        # metrics
        train_loss += loss.item()
        prediction = torch.argmax(output, 1)
        train_acc += (prediction == target).sum().item()/len(prediction)
        total += 1
       
    return train_loss, train_acc

def validate_epoch(model, test_dataloader, loss_fn, device):
    test_loss = 0.0
    test_acc = 0.0
    total = 0.0

    model.eval()

    with torch.no_grad():
        for wav, target in tqdm(test_dataloader, "Testing batch..."):
            wav, target = wav.to(device), target.to(device)

            output = model(wav)
            loss = loss_fn(output, target)

            test_loss += loss.item()
            prediciton = torch.argmax(output, 1)
            test_acc += (prediciton == target).sum().item()/len(prediciton)
            total += 1
    
    return test_loss, test_acc

if __name__ == "__main__":
    if torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
    print(f"Using {device} device.")

    # instantiating our dataset object and create data loader
    mel_spectrogram = torchaudio.transforms.MelSpectrogram(
        sample_rate=SAMPLE_RATE,
        n_fft=2048,
        hop_length=512,
        n_mels=128
    )

    train_dataset = VoiceDataset(AISF_TRAIN_FILE, mel_spectrogram, device, time_limit_in_secs=3)
    train_dataloader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)

    # construct model
    model = CNNetwork().to(device)
    print(model)
    print(train_dataset.label_mapping)

    # init loss function and optimizer
    loss_fn = nn.CrossEntropyLoss()
    # optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    optimizer = torch.optim.SGD(model.parameters(), lr=LEARNING_RATE, momentum=0.9)

    wandb.init(project="void-train")

    # train model
    train(model, train_dataloader, loss_fn, optimizer, device, EPOCHS)

    model.label_mapping = train_dataset.label_mapping

    # save model
    now = datetime.now()
    now = now.strftime("%Y%m%d_%H%M%S")
    model_filename = f"models/aisf/void_{now}.pth"
    torch.save(model.state_dict(), model_filename)
    print(f"Trained void model saved at {model_filename}")
    wandb.finish()