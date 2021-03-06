#including relu activaton and dropout after the first linear layer
# prototype of gru network for pedestrian modeling
# written by: Ashish Roongta, Fall 2018
# carnegie mellon university

# import relevant libraries
import torch
import torch.nn as nn
import torch.optim as optim
import matplotlib
import numpy as np
import trajectories
import loader
import argparse
import gc
import logging
import os
import sys
import time
import matplotlib.pyplot as plt 

# build argparser
parser = argparse.ArgumentParser()

parser.add_argument('--input_size', type=int, default=2)
parser.add_argument('--output_size', type=int, default=2)
# RNN size parameter (dimension of the output/hidden state)
parser.add_argument('--rnn_size', type=int, default=128,
                 help='size of RNN hidden state')
# size of each batch parameter
parser.add_argument('--batch_size', type=int, default=5,
                 help='minibatch size')
# Length of sequence to be considered parameter
parser.add_argument('--seq_length', type=int, default=20,
                 help='RNN sequence length')
parser.add_argument('--pred_length', type=int, default=12,
                 help='prediction length')
# number of epochs parameter
parser.add_argument('--num_epochs', type=int, default=20,
                 help='number of epochs')
# frequency at which the model should be saved parameter
parser.add_argument('--save_every', type=int, default=400,
                 help='save frequency')
# gradient value at which it should be clipped
parser.add_argument('--grad_clip', type=float, default=10.,
                 help='clip gradients at this value')
# learning rate parameter
parser.add_argument('--learning_rate', type=float, default=0.003,
                 help='learning rate')
# decay rate for the learning rate parameter
parser.add_argument('--decay_rate', type=float, default=0.95,
                 help='decay rate for rmsprop')
# dropout probability parameter
parser.add_argument('--dropout', type=float, default=0.5,
                 help='dropout probability')
# dimension of the embeddings parameter
parser.add_argument('--embedding_size', type=int, default=64,
                 help='Embedding dimension for the spatial coordinates')
# size of neighborhood to be considered parameter
parser.add_argument('--neighborhood_size', type=int, default=32,
                 help='Neighborhood size to be considered for social grid')
# size of the social grid parameter
parser.add_argument('--grid_size', type=int, default=4,
                 help='Grid size of the social grid')
# maximum number of pedestrians to be considered
parser.add_argument('--maxNumPeds', type=int, default=27,
                 help='Maximum Number of Pedestrians')

# lambda regularization parameter (L2)
parser.add_argument('--lambda_param', type=float, default=0.0005,
                 help='L2 regularization parameter')
# cuda parameter

# GRU parameter
parser.add_argument('--gru', action="store_true", default=False,
                 help='True : GRU cell, False: gru cell')
# drive option
parser.add_argument('--drive', action="store_true", default=False,
                 help='Use Google drive or not')
# number of validation will be used
parser.add_argument('--num_validation', type=int, default=2,
                 help='Total number of validation dataset for validate accuracy')
# frequency of validation
parser.add_argument('--freq_validation', type=int, default=1,
                 help='Frequency number(epoch) of validation using validation data')
# frequency of optimizer learning decay
parser.add_argument('--freq_optimizer', type=int, default=8,
                 help='Frequency number(epoch) of learning decay for optimizer')
# store grids in epoch 0 and use further.2 times faster -> Intensive memory use around 12 GB
parser.add_argument('--grid', action="store_true", default=True,
                 help='Whether store grids and use further epoch')

# dataset options
parser.add_argument('--dataset_name', default='eth', type=str)
parser.add_argument('--delim', default='\t')
parser.add_argument('--loader_num_workers', default=4, type=int)
parser.add_argument('--obs_len', default=8, type=int)
parser.add_argument('--pred_len', default=12, type=int)
parser.add_argument('--skip', default=1, type=int)
parser.add_argument('--use_cuda', action="store_true", default=False,help='Use GPU or not')

args = parser.parse_args()

cur_dataset = args.dataset_name

data_dir = os.path.join('/mnt/h/Ashish/ped_trajectory_prediction/sgan_ab/scripts/datasets/', cur_dataset + '/train')

''' Class for defining the GRU Network '''
class GRUNet(nn.Module):
    def __init__(self):
        super(GRUNet, self).__init__()
        
        ''' Inputs to the GRUCell's are (input, (h_0, c_0)):
         1. input of shape (batch, input_size): tensor containing input 
         features
         2a. h_0 of shape (batch, hidden_size): tensor containing the 
         initial hidden state for each element in the batch.
         2b. c_0 of shape (batch, hidden_size): tensor containing the 
         initial cell state for each element in the batch.
        
         Outputs: h_1, c_1
         1. h_1 of shape (batch, hidden_size): tensor containing the next 
         hidden state for each element in the batch
         2. c_1 of shape (batch, hidden_size): tensor containing the next 
         cell state for each element in the batch '''
        
        # set parameters for network architecture
        self.embedding_size = 64
        self.rnn_size=128
        self.input_size = 2
        self.output_size = 2
        self.dropout_prob = 0.5
        if(args.use_cuda):
            self.device = torch.device("cuda:0") # to run on GPU
        else:
            self.device=torch.device("cpu")

        # linear layer to embed the input position
        self.input_embedding_layer = nn.Linear(self.input_size, self.embedding_size)
        
        # define gru cell
        self.gru_cell = nn.GRUCell(self.embedding_size, self.rnn_size)

        # linear layer to map the hidden state of gru to output
        self.output_layer = nn.Linear(self.rnn_size, self.output_size)
        
        # ReLU and dropout unit
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(self.dropout_prob)
        
        pass
 
    def forward(self, observed_batch, pred_len = 0):
        ''' this function takes the input sequence and predicts the output sequence. 
        
            args:
                observed_batch (torch.Tensor) : input batch with shape <seq length x num pedestrians x number of dimensions>
                pred_len (int) : length of the sequence to be predicted.

        '''
        output_seq = []

        ht = torch.zeros(observed_batch.size(1), self.rnn_size,device=self.device, dtype=torch.float)
        ct = torch.zeros(observed_batch.size(1), self.rnn_size,device=self.device, dtype=torch.float)
        seq, peds, coords = observed_batch.shape

        # feeding the observed trajectory to the network
        for step in range(seq):
            observed_step = observed_batch[step, :, :]
            lin_out = self.input_embedding_layer(observed_step.view(peds,2))
            input_embedded=self.dropout(self.relu(lin_out))
            ht = self.gru_cell(input_embedded, ht)
            out = self.output_layer(ht)

        # getting the predicted trajectory from the pedestrian 
        for i in range(pred_len):
            lin_out = self.input_embedding_layer(out)
            input_embedded=self.dropout(self.relu(lin_out))
            ht= self.gru_cell(input_embedded, ht)
            out = self.output_layer(ht)
            output_seq += [out]
            
        output_seq = torch.stack(output_seq).squeeze() # convert list to tensor
        return output_seq

# test function to calculate and return avg test loss after each epoch
def test(gru_net,args,pred_len=0):

    test_data_dir = os.path.join('/mnt/h/Ashish/ped_trajectory_prediction/sgan_ab/scripts/datasets/', cur_dataset + '/test')

    # retrieve dataloader
    dataset, dataloader = loader.data_loader(args, test_data_dir)

    # define parameters for training and testing loops
    criterion = nn.MSELoss() # MSE works best for difference between predicted and actual coordinate paths
    num_test_peds=0 #counter for the number of pedestrians in the test data
    # initialize lists for capturing losses
    test_loss = []
    test_avgD_error=[]
    test_finalD_error=[]
   
    # now, test the model
    for i, batch in enumerate(dataloader):
        if(args.use_cuda):
            test_observed_batch = batch[0].cuda()
            test_target_batch = batch[1].cuda()
        else:
            test_observed_batch = batch[0]
            test_target_batch = batch[1]

        out = gru_net(test_observed_batch, pred_len=pred_len) # forward pass of gru network for training
        cur_test_loss = criterion(out, test_target_batch) # calculate MSE loss
        test_loss.append(cur_test_loss.item())
        out1=out
        target_batch1=test_target_batch  #making a copy of the tensors to convert them to array
        if(args.use_cuda):
            out1=out1.cpu()
            target_batch1=target_batch1.cpu()
        
        seq, peds, coords = test_target_batch.shape
        num_test_peds+=peds
        avgD_error=(np.sum(np.sqrt(np.square(out1[:,:,0].detach().numpy()-target_batch1[:,:,0].detach().numpy())+
            np.square(out1[:,:,1].detach().numpy()-target_batch1[:,:,1].detach().numpy()))))/(pred_len*peds)
        test_avgD_error.append(avgD_error)

        # final displacement error
        finalD_error=(np.sum(np.sqrt(np.square(out1[pred_len-1,:,0].detach().numpy()-target_batch1[pred_len-1,:,0].detach().numpy())+
            np.square(out1[pred_len-1,:,1].detach().numpy()-target_batch1[pred_len-1,:,1].detach().numpy()))))/peds
        test_finalD_error.append(finalD_error)
                
    avg_testloss = sum(test_loss)/len(test_loss)
    avg_testD_error=sum(test_avgD_error)/len(test_avgD_error)
    avg_testfinalD_error=sum(test_finalD_error)/len(test_finalD_error)
    print("============= Average test loss:", avg_testloss, "====================")


    return avg_testloss, avg_testD_error,avg_testfinalD_error,num_test_peds



def main(args):
    
    '''define parameters for training and testing loops!'''

    # num_epoch = 20
    # pred_len = 12
    # learning_rate = 0.001
    # load trained model, if applicable
# if (cur_dataset != "eth"):
#     print("loading data from {}...".format(cur_dataset))
#     gru_net = torch.load('./saved_models/gru_model_' + cur_dataset + '_lr_0025_epoch_100_predlen_12.pt')
#     gru_net.eval() # set dropout and batch normalization layers to evaluation mode before running inference

    num_epoch = args.num_epochs
    pred_len = args.pred_len
    learning_rate = args.learning_rate
    obs_len=args.obs_len
    # retrieve dataloader
    dataset, dataloader = loader.data_loader(args, data_dir)

    ''' define the network, optimizer and criterion '''
    name=cur_dataset # to add to the name of files
    # if (cur_dataset == "eth"):
    gru_net = GRUNet()
    if(args.use_cuda):
        gru_net.cuda()


    criterion = nn.MSELoss() # MSE works best for difference between predicted and actual coordinate paths
    optimizer = optim.Adam(gru_net.parameters(), lr=learning_rate)

    # initialize lists for capturing losses/errors
    train_loss = []
    test_loss = []
    avg_train_loss = []
    avg_test_loss = []
    train_avgD_error=[]
    train_finalD_error=[]
    avg_train_avgD_error=[]
    avg_train_finalD_error=[]
    test_finalD_error=[]
    test_avgD_error=[]
    std_train_loss = []
    std_test_loss = []
    num_train_peds=[] #counter for the number of pedestrians in the training data

    '''training loop'''
    for i in range(num_epoch):
        print('======================= Epoch: {cur_epoch} / {total_epochs} =======================\n'.format(cur_epoch=i, total_epochs=num_epoch))
        def closure():
            train_peds=0 #counter for the number of pedestrians in the training data
            for i, batch in enumerate(dataloader):
                if(args.use_cuda):
                    train_batch = batch[0].cuda()
                    target_batch = batch[1].cuda()
                else:
                    train_batch = batch[0]
                    target_batch = batch[1]
                # print("train_batch's shape", train_batch.shape)
                # print("target_batch's shape", target_batch.shape)
                seq, peds, coords = train_batch.shape # q is number of pedestrians
                train_peds+=peds 
                out = gru_net(train_batch, pred_len=pred_len) # forward pass of gru network for training
                # print("out's shape:", out.shape)
                optimizer.zero_grad() # zero out gradients
                cur_train_loss = criterion(out, target_batch) # calculate MSE loss
                # print('Current training loss: {}'.format(cur_train_loss.item())) # print current training loss
                print('Current training loss: {}'.format(cur_train_loss.item())) # print current training loss
                
                #calculating average deisplacement error
                out1=out
                target_batch1=target_batch  #making a copy of the tensors to convert them to array
                if(args.use_cuda):
                    out1=out1.cpu()
                    target_batch1=target_batch1.cpu()
                avgD_error=(np.sum(np.sqrt(np.square(out1[:,:,0].detach().numpy()-target_batch1[:,:,0].detach().numpy())+
                    np.square(out1[:,:,1].detach().numpy()-target_batch1[:,:,1].detach().numpy()))))/(pred_len*peds)
                train_avgD_error.append(avgD_error)

                #calculate final displacement error
                finalD_error=(np.sum(np.sqrt(np.square(out1[pred_len-1,:,0].detach().numpy()-target_batch1[pred_len-1,:,0].detach().numpy())+
                    np.square(out1[pred_len-1,:,1].detach().numpy()-target_batch1[pred_len-1,:,1].detach().numpy()))))/peds
                train_finalD_error.append(finalD_error)

                train_loss.append(cur_train_loss.item())
                cur_train_loss.backward() # backward prop
                optimizer.step() # step like a mini-batch (after all pedestrians)
            num_train_peds.append(train_peds)
            return cur_train_loss
        optimizer.step(closure) # update weights

        # save model at every epoch (uncomment) 
        # torch.save(gru_net, './saved_models/gru_model_v3.pt')
        # print("Saved gru_net!")
        avg_train_loss.append(np.sum(train_loss)/len(train_loss))
        avg_train_avgD_error.append(np.sum(train_avgD_error)/len(train_avgD_error))
        avg_train_finalD_error.append(np.sum(train_finalD_error)/len(train_finalD_error))   
        std_train_loss.append(np.std(np.asarray(train_loss)))
        train_loss = [] # empty train loss

        print("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$")
        print("average train loss: {}".format(avg_train_loss))
        print("average std loss: {}".format(std_train_loss))
        avgTestLoss,avgD_test,finalD_test,num_test_peds=test(gru_net,args,pred_len)
        avg_test_loss.append(avgTestLoss)
        test_finalD_error.append(finalD_test)
        test_avgD_error.append(avgD_test)
        print("test finalD error: ",finalD_test)
        print("test avgD error: ",avgD_test)
        print("Number of pedestrians: {}".format(num_train_peds))
        #avg_test_loss.append(test(gru_net,args,pred_len)) ##calliing test function to return avg test loss at each epoch


    '''after running through epochs, save your model and visualize.
       then, write your average losses and standard deviations of 
       losses to a text file for record keeping.'''

    save_path = os.path.join('./saved_models/', 'gru_model_'+name+'_lr_' + str(learning_rate) + '_epoch_' + str(num_epoch) + '_predlen_' + str(pred_len) +'_obs'+str(obs_len)+ '.pt')
    # torch.save(gru_net, './saved_models/gru_model_lr001_ep20.pt')
    torch.save(gru_net, save_path)
    print("saved gru_net! location: " + save_path)

    ''' visualize losses vs. epoch'''
    plt.figure() # new figure
    plt.title("Average train loss vs {} epochs".format(num_epoch))
    plt.plot(avg_train_loss,label='avg train_loss') 
    plt.plot(avg_test_loss,color='red',label='avg test_loss')
    plt.legend()
    plt.savefig("./saved_figs/" + "gru_"+name+"_avgtrainloss_lr_"+ str(learning_rate) + '_epochs_' + str(num_epoch) + '_predlen_' + str(pred_len) +'_obs'+str(obs_len)+  '.png')
    # plt.show()
    # plt.show(block=True)
    
    plt.figure() # new figure
    plt.title("Average and final displacement error {} epochs".format(num_epoch))
    plt.plot(avg_train_finalD_error,label='train:final disp. error') 
    plt.plot(avg_train_avgD_error,color='red',label='train:avg disp. error')
    plt.plot(test_finalD_error,color='green',label='test:final disp. error')
    plt.plot(test_avgD_error,color='black',label='test:avg disp. error')
    plt.ylim((0,10))
    plt.legend()
    # plt.show()
    plt.savefig("./saved_figs/" + "gru_"+name+"_avg_final_displacement_lr_"+ str(learning_rate) + '_epochs_' + str(num_epoch) + '_predlen_' + str(pred_len) +'_obs'+str(obs_len)+  '.png')

    plt.figure()
    plt.title("Std of train loss vs epoch{} epochs".format(num_epoch))
    plt.plot(std_train_loss)
    plt.savefig("./saved_figs/" + "gru_"+name+"_stdtrainloss_lr_"+ str(learning_rate) + '_epochs_' + str(num_epoch) + '_predlen_' + str(pred_len) +'_obs'+str(obs_len)+'.png')
    # plt.show(block=True)
    print("saved images for avg training losses! location: " + "./saved_figs")

    # save results to text file
    txtfilename = os.path.join("./txtfiles/", "gru_"+name+"_avgtrainlosses_lr_"+ str(learning_rate) + '_epochs_' + str(num_epoch) + '_predlen_' + str(pred_len) +'_obs'+str(obs_len)+ ".txt")
    os.makedirs(os.path.dirname("./txtfiles/"), exist_ok=True) # make directory if it doesn't exist
    with open(txtfilename, "w") as f:
        f.write("Number of pedestrians in the training data: {}\n".format(num_train_peds[-1]))    
        f.write("Number of pedestrians in the testing data: {}\n".format(num_test_peds))  
        f.write("\n==============Average train loss vs. epoch:===============\n")
        f.write(str(avg_train_loss))
        f.write("\nepochs: " + str(num_epoch))
        f.write("\n==============Std train loss vs. epoch:===================\n")
        f.write(str(std_train_loss))
        f.write("\n==============Avg test loss vs. epoch:===================\n")
        f.write(str(avg_test_loss))
        f.write("\n==============Avg train displacement error:===================\n")
        f.write(str(avg_train_avgD_error))
        f.write("\n==============Final train displacement error:===================\n")
        f.write(str(avg_train_finalD_error))
        f.write("\n==============Avg test displacement error:===================\n")
        f.write(str(test_avgD_error))
        f.write("\n==============Final test displacement error:===================\n")
        f.write(str(test_finalD_error))
    print("saved average and std of training losses to text file in: ./txtfiles")
    
    # #saving all the data for different observed lengths    
    # txtfilename2 = os.path.join("./txtfiles/", "gru_"+name+"_diff_observed_len_lr_"+ str(learning_rate) + '_epochs_' + str(num_epoch) + '_predlen_' + str(pred_len) + ".txt")
    # os.makedirs(os.path.dirname("./txtfiles/"), exist_ok=True) # make directory if it doesn't exist
    # with open(txtfilename2,"a+") as g: #opening the file in the append mode
    #     if(obs_len==2):
    #         g.write("obs_len"+"\t"+"avg_train_loss"+"\t"+"avg_test_loss"+"\t"+"avg_train_dispacement"
    #             +"\t"+"final_train_displacement"+"\t"+"avg_test_displacement"+"\t"+"final_test_displacement"+"\n")
    #     # outputing the current observed length
    #     g.write(str(obs_len)+"\t")
    #     #the avg_train_loss after total epochs
    #     g.write(str(avg_train_loss[-1])+"\t")
    #     # the avg_test_loss after total epochs
    #     g.write(str(avg_test_loss[-1])+"\t")
    #     # the avg train dispacement error
    #     g.write(str(avg_train_avgD_error[-1])+"\t")
    #     # the train final displacement error
    #     g.write(str(avg_train_finalD_error[-1])+"\t")
    #     # the test avg displacement error
    #     g.write(str(test_avgD_error[-1])+"\t")
    #     # the test final displacement error
    #     g.write(str(test_finalD_error[-1])+"\n")
    # print("saved all the results to the text file for observed length: {}".format(obs_len))
    txtfilename2 = os.path.join("./txtfiles/", "GRU_RESULTS"+name+"_diff_obs_pred_len_lr_"+ str(learning_rate) + '_epochs_' + str(num_epoch)+ ".txt")
    os.makedirs(os.path.dirname("./txtfiles/"), exist_ok=True) # make directory if it doesn't exist
    with open(txtfilename2,"a+") as g: #opening the file in the append mode
        if(pred_len==2):
            g.write("Dataset: "+name+" ;Number of epochs: {}".format(num_epoch)+"\n")
            g.write("obs_len"+"\t"+"pred_len"+"\t"+"avg_train_loss"+"\t"+"avg_test_loss"+"\t"+"std_train_loss"+"\t"
                +"avg_train_dispacement"+"\t"+"final_train_displacement"+"\t"+"avg_test_displacement"+"\t"+
                "final_test_displacement"+"Num_Train_peds"+"\t"+"Num_Test_Peds"+"\n")
        # outputing the current observed length
        g.write(str(obs_len)+"\t")
        # outputing the current prediction length
        g.write(str(pred_len)+"\t")
        #the avg_train_loss after total epochs
        g.write(str(avg_train_loss[-1])+"\t")
        # the avg_test_loss after total epochs
        g.write(str(avg_test_loss[-1])+"\t")
        # the standard deviation of train loss
        g.write(str(std_train_loss[-1])+"\t")
        # the avg train dispacement error
        g.write(str(avg_train_avgD_error[-1])+"\t")
        # the train final displacement error
        g.write(str(avg_train_finalD_error[-1])+"\t")
        # the test avg displacement error
        g.write(str(test_avgD_error[-1])+"\t")
        # the test final displacement error
        g.write(str(test_finalD_error[-1])+"\t")
        # the number of pedestrians in the traininig dataset
        g.write(str(num_train_peds[-1])+"\t")
        # Number of pedestrian sin the training dataset
        g.write(str(num_test_peds)+"\n")
    print("saved all the results to the text file for observed length: {}".format(obs_len))

'''main function'''
if __name__ == '__main__':
    main(args)

