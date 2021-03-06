import numpy as np
import matplotlib.pyplot as plt
import os
## for LSTM errors v/s prediction length 
learning_rate=0.0007
name="em64rnn128" # to add to the name of files
pred_len=8
num_epoch=100
filename="gru_"+name+"_diff_observed_len_lr_"+ str(learning_rate) + '_epochs_' + str(num_epoch) + '_predlen_' + str(pred_len)
file_path1 = os.path.join("./txtfiles/",filename+".txt")
Data_headings=open(file_path1) #Reading the file in string format
line =Data_headings.readline() #Extracting the first line of the file
headers=line.split() #extracting each column header form the first line
Data_headings.close() #closing the file
Data=np.genfromtxt(file_path1) #reading the txt file in float datatype
r,c=Data.shape #computing the dimensions of the file

# For avg test and train loss v/s observation length
plt.figure(1)
for i in range(1,3):
	plt.plot(Data[1:r,0],Data[1:r,i],label=headers[i],linewidth=5)
plt.title("Losses v/s observed length(prediction length:{}".format(pred_len))
plt.xlim((Data[1,0],Data[-1,0]))
plt.xlabel("Observation Length")
plt.ylabel("Losses/Errors")
plt.grid()
plt.legend()
file_path2=os.path.join("./saved_figs/","avg_loss_"+filename+".jpeg")
plt.savefig(file_path2)
print("Plot saved: ",file_path2)

# For test & train avg and final displacement v/s observation length 
plt.figure(2)
for i in range(3,c):
	plt.plot(Data[1:r,0],Data[1:r,i],label=headers[i],linewidth=5)
plt.title("Losses v/s observed length(prediction length:{}".format(pred_len))
plt.xlim((Data[1,0],Data[-1,0]))
plt.xlabel("Observation Length")
plt.ylabel("Losses/Errors")
plt.grid()
plt.legend()
file_path2=os.path.join("./saved_figs/","disp_loss_"+filename+".jpeg")
plt.savefig(file_path2)
print("Plot saved: ",file_path2)

##For GRU, error v/s prediction length

# filename="./txtfiles/gru_results_100epoch_lr0.0017"
# data=np.genfromtxt(filename)
# r,c=data.shape
# plt.plot(data[:,0],data[:,1],label="Avg. test loss",color='r',linewidth=5)
# plt.plot(data[:,0],data[:,2],label="Avg. displacement error",color='g',linewidth=5)
# plt.plot(data[:,0],data[:,3],label="Final Displacement Error",color='blue',linewidth=5)
# plt.xlabel("Predicted Trajectory length")
# plt.ylabel("Errors")
# plt.legend()
# plt.show(block=True)
