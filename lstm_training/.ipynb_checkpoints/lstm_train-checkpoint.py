import argparse
import json
import os
import pickle
import sys
import sagemaker_containers
import pandas as pd
import torch
import torch.optim as optim
import torch.utils.data

from model_lstm import LSTMClassifier,csr_to_torch_long,y_torch

def model_fn(model_dir):
    """Load the PyTorch model from the `model_dir` directory."""
    print("Loading model.")

    # First, load the parameters used to create the model.
    model_info = {}
    model_info_path = os.path.join(model_dir, 'model_info.pth')
    with open(model_info_path, 'rb') as f:
        model_info = torch.load(f)

    print("model_info: {}".format(model_info))

    # Determine the device and construct the model.
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = LSTMClassifier(model_info['vocab_size'],model_info['embedding_dim'], model_info['hidden_dim'],model_info['output_dim'])

    # Load the stored model parameters.
    model_path = os.path.join(model_dir, 'model.pth')
    with open(model_path, 'rb') as f:
        model.load_state_dict(torch.load(f))

    model.to(device).eval()

    print("Done loading model.")
    return model

def _get_train_data_loader(batch_size, training_dir):
    print("Get train data loader.")
    
    x_train_path=os.path.join(training_dir, "x_train.pkl")
    y_train_path=os.path.join(training_dir, "y_train.pkl")
    
    x_train=pickle.load(open(x_train_path,'rb'))
    y_train=pickle.load(open(y_train_path,'rb'))

    train_ds = torch.utils.data.TensorDataset(csr_to_torch_long(x_train).to_dense(), y_torch(y_train))

    return torch.utils.data.DataLoader(train_ds, batch_size=batch_size)


def train(model, train_loader, epochs, optimizer, loss_fn, device):
    """
    This is the training method that is called by the PyTorch training script. The parameters
    passed are as follows:
    model        - The PyTorch model that we wish to train.
    train_loader - The PyTorch DataLoader that should be used during training.
    epochs       - The total number of epochs to train for.
    optimizer    - The optimizer to use during training.
    loss_fn      - The loss function used for training.
    device       - Where the model and data should be loaded (gpu or cpu).
    """

    # TODO: Paste the train() method developed in the notebook here.
    for epoch in range(1, epochs + 1):
            model.train()
            total_loss = 0
            for batch in train_loader:
                batch_X, batch_y = batch

                batch_X = batch_X.to(device)
                batch_y = batch_y.to(device)

                # TODO: Complete this train method to train the model provided.
                optimizer.zero_grad()
                predictions=model(batch_X)

                loss=loss_fn(predictions,batch_y)

                total_loss += loss.data.item()
                loss.backward()
                optimizer.step()

            print("Epoch: {}, CELoss: {}".format(epoch, total_loss / len(train_loader)))



if __name__ == '__main__':
    # All of the model parameters and training parameters are sent as arguments when the script
    # is executed. Here we set up an argument parser to easily access the parameters.

    parser = argparse.ArgumentParser()

    # Training Parameters
    parser.add_argument('--batch-size', type=int, default=512, metavar='N',
                        help='input batch size for training (default: 512)')
    parser.add_argument('--epochs', type=int, default=10, metavar='N',
                        help='number of epochs to train (default: 10)')
    parser.add_argument('--seed', type=int, default=1, metavar='S',
                        help='random seed (default: 1)')

    # Model Parameters
    parser.add_argument('--embedding_dim', type=int, default=100, metavar='N',
                        help='size of the word embeddings (default: 32)')
    parser.add_argument('--hidden_dim', type=int, default=100, metavar='N',
                        help='size of the hidden dimension (default: 100)')
    parser.add_argument('--vocab_size', type=int, default=5000, metavar='N',
                        help='size of the vocabulary (default: 5000)')
    parser.add_argument('--output_dim',type=int,default=3,metavar='N',
                        help='output dimension (default: 3)')

    # SageMaker Parameters
    parser.add_argument('--hosts', type=list, default=json.loads(os.environ['SM_HOSTS']))
    parser.add_argument('--current-host', type=str, default=os.environ['SM_CURRENT_HOST'])
    parser.add_argument('--model-dir', type=str, default=os.environ['SM_MODEL_DIR'])
    parser.add_argument('--data-dir', type=str, default=os.environ['SM_CHANNEL_TRAINING'])
    parser.add_argument('--num-gpus', type=int, default=os.environ['SM_NUM_GPUS'])

    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Using device {}.".format(device))

    torch.manual_seed(args.seed)

    # Load the training data.
    train_loader = _get_train_data_loader(args.batch_size, args.data_dir)

    # Build the model.
    model = LSTMClassifier(args.vocab_size,args.embedding_dim, args.hidden_dim,args.output_dim).to(device)

    print("Model loaded with embedding_dim {}, hidden_dim {}, vocab_size {}, output_dim {}".format(
        args.embedding_dim, args.hidden_dim, args.vocab_size, args.output_dim
    ))

    # Train the model.
    optimizer = optim.Adam(model.parameters())
    loss_fn = torch.nn.CrossEntropyLoss()

    train(model, train_loader, args.epochs, optimizer, loss_fn, device)

    # Save the parameters used to construct the model
    model_info_path = os.path.join(args.model_dir, 'model_info.pth')
    with open(model_info_path, 'wb') as f:
        model_info = {
            'epochs':args.epochs,
            'embedding_dim': args.embedding_dim,
            'hidden_dim': args.hidden_dim,
            'vocab_size': args.vocab_size,
            'output_dim':args.output_dim
        }
        torch.save(model_info, f)

	# Save the model parameters
    model_path = os.path.join(args.model_dir, 'model.pth')
    with open(model_path, 'wb') as f:
        torch.save(model.cpu().state_dict(), f)
