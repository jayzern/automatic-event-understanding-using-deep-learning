## Team2 Github Readme

### Dependencies
- Python 3.7
- Tensorflow 2.3.0
- CUDA 11.0
- Numpy
- nltk

### Setup on Google Cloud VM for Training
1. Request for GPU quota increase
2. Use Deep Learning VM (https://console.cloud.google.com/marketplace/product/click-to-deploy-images/deeplearning) -> Click Launch
3. Give the VM a name, select zone (US-central1-b), select machine type (4vCPUs, 15GB memory n1-standard-4) select GPU type (NVIDIA Tesla T4)
4. Ensure that framework selected is Tensorflow 2.3.0 with CUDA 11.0
5. Check the checkbox to install NVIDIA GPU driver automatically on first startup
6. Boot disk of 100GB is enough for training

#### Screenshot of Deep Learning VM Setup <br/>
<img src=https://github.com/15huangtimothy/bloomberg-event-embedding-team2/blob/master/setup_gcloud.JPG width=300 height=400/>

### Setup Google Cloud bucket to store files (optional)
1. Create 3 different storage buckets (one for training scripts, one for preprocessed data, one for trained model weights)
2. setup of the three buckets <br/>
    a. Training script bucket
    - Pull from github and arrange files like the one in the following directory. data, model and results folder should be initially empty. Upload directory into the first bucket.
    ```
    ├── data
    ├── model
    ├── results
    ├── eval_data
    └── event-embedding
        ├── main2.py
        ├── config.py
        ├── utils.py
        ├── batcher.py
        ├── model
        │   ├── __init__.py
        │   ├── embeddings.py
        │   ├── layers.py
        │   ├── generic.py
        │   ├── resrofa.py
        │   └── ...
        ├── evaluation
        │   ├── __init__.py
        │   └── ...
        └── README.md
    ```    
    b. Data Bucket
    - below is a list of all the dataset available. Arrange all the folders into one directory and upload to the second bucket.
    ```
    ├── exp9_0.001-16-16-Roles2Args3Mods-NoFrAn-v1
    ├── exp9_0.001-16-16-Roles2Args3Mods-NoFrAn-v2
    ├── exp9_0.01-16-16-Roles2Args3Mods-NoFrAn-v1
    ├── exp9_0.01-16-16-Roles2Args3Mods-NoFrAn-v2
    ├── exp9_0.1-16-16-Roles2Args3Mods-NoFrAn-v1
    ├── exp9_0.1-16-16-Roles2Args3Mods-NoFrAn-v1 (renamed from exp7_0.1-16-16-NoFrAn-v2)
    ├── worder_exp9_0.001-16-16-Roles2Args3Mods-NoFrAn-v1
    ├── worder_exp9_0.001-16-16-Roles2Args3Mods-NoFrAn-v2
    ├── worder_exp9_0.01-16-16-Roles2Args3Mods-NoFrAn-v1
    ├── worder_exp9_0.01-16-16-Roles2Args3Mods-NoFrAn-v2
    ├── worder_exp9_0.1-16-16-Roles2Args3Mods-NoFrAn-v1
    └── worder_exp9_0.1-16-16-Roles2Args3Mods-NoFrAn-v2  
    ```
    c. Trained weights Bucket
    - Initially will be empty, but trained model weights will be saved here. Create a folder inside the bucket to store the trained model weights and logs.


## Team2 Setup for Training (Python3.7 and TF2.3.0)
1. SSH into Deployed Deep Learning VM
2. Pull code from Github/Google Cloud Bucket and arrange into the following directory
#### File arrangements
* All files should be organized in following structure.
* Note: If pulling from Google Cloud Bucket (Authenticate using command: gcloud auth login)
* model and results folder should be initially empty if we are trainining models. 
* If some of the folders don't exist create one using (sudo mkdir folder_name)
    ```
    ├── data
        │   ├── exp9_0.1-16-16-Roles2Args3Mods-NoFrAn-v1
        │   └── ... (all other data folders needed for training) 
    ├── model
    ├── results
    ├── eval_data
    └── event-embedding
        ├── main2.py
        ├── config.py
        ├── utils.py
        ├── batcher.py
        ├── model
        │   ├── __init__.py
        │   ├── embeddings.py
        │   ├── layers.py
        │   ├── generic.py
        │   ├── resrofa.py
        │   └── ...
        ├── evaluation
        │   ├── __init__.py
        │   └── ...
        └── README.md
    ```
2. Install dependencies (If not already present). All other dependencies should come preinstalled from Deep Learning VM module.
    - Numpy
    ```
    pip install numpy
    ```
    - NLTK (Go to python mode by typing in "python" in command line followed by the commands below)
    ```
    import nltk
    nltk.download('all')
    ```
4. move into directory of main2.py file
```
cd event-embedding
```
4. Training commands
- Without Screen command
```
python3 main2.py MODEL_NAME DATA_FOLDER_NAME EXPERIMENT_NAME \
      --epochs NUM_EPOCHS --batch_size BATCH_SIZE --role_set Roles2Args3Mods
```
- With Screen command (to allow training to continue after ending ssh session)
```
screen -s workspace -L LOG_NAME python3 main2.py MODEL_NAME DATA_FOLDER_NAME EXPERIMENT_NAME \
      --epochs NUM_EPOCHS --batch_size BATCH_SIZE --role_set Roles2Args3Mods
```
- Parameters Explanation
    - MODEL_NAME = name of model used for training (Ex: MTRFv4Rex)
    - DATA_FOLDER_NAME = name of data folder (Ex: exp9_0.1-16-16-Roles2Args3Mods-NoFrAn-v1)
    - EXPERIMENT_NAME = name of experiment (Ex: 20200717-batch1024-iters25)
    - NUM_EPOCHS = number of epochs used for training (Ex: 25). Note: training can last less than NUM_EPOCHS due to early stopping
    - BATCH_SIZE = batchsize used for experiment (Ex: 1024)
    - LOG_NAME = log name txt file (Ex: log_0.1v1_resrofa_trial1.txt)
    
- Example commands for ResRoFa without screen command (Baseline)
```
python3 main2.py MTRFv4Res exp9_0.1-16-16-Roles2Args3Mods-NoFrAn-v1 20200717-batch1024-iters25 \
        --epochs 25 --batch_size 1024 --role_set Roles2Args3Mods
```
- Example commands for ResRoFa with screen command (Baseline)
```
screen -s workspace -L log_0.1v1_resrofa_trial1.txt python3 main2.py MTRFv4Res \ 
        exp9_0.1-16-16-Roles2Args3Mods-NoFrAn-v1 20200717-batch1024-iters25 \
        --epochs 25 --batch_size 1024 --role_set Roles2Args3Mods
```
- Table of all model name, model file, model name command, and data used

| Model Name | Model File | Model Name Command | Data Used |
| ------------- | ------------- | ------------- | ------------- | 
| ResRofa-MT  | resrofa.py  | MTRFv4Res  | exp9...  |
| RoFDense  | rofdense.py  | MTRFv4ResDense  | exp9...  |
| RoFBeg  | rofbeg.py  | MTRFv4RofBeg  | exp9...  |
| RoFWD  | rofawd.py  | MTRFv4WD  | exp9...  |
| ResRoFDense  | rofdense_v2.py  | MTRFv4ResDense_v2  | exp9...  |
| ResRoFBeg  | rofbeg_v2.py  | MTRFv4RofBeg_v2  | exp9...  |
| ResRoFWD  | ?  | ?  | exp9...  |
| ResRoFSeqRNN  | rofseqrnn.py  | MTRFv4RofSeqRNN | worder_exp9...  |
| ResRoFSeqLSTM  | rofseqlstm.py  | MTRFv4RofSeqLSTM | worder_exp9...  |
| ResRoFSeqBiLSTM  | rofseqbilstm.py  | MTRFv4RofSeqBiLSTM | worder_exp9...  |
| ResRoFSeqBiLSTMDense  | rofseqbilstmdense.py  | MTRFv4RofSeqBiLSTMDense | worder_exp9...  |
| ResRoFSeqBiLSTMAt  | rofseqbilstmat.py  | MTRFv4RofSeqBiLSTMAt | worder_exp9...  |
| ResRoFSeqAt  | rofseqat.py  | MTRFv4RofSeqAt | worder_exp9...  |
| ResRoFSeqAtDot  | rofseqatdot.py  | MTRFv4RofSeqAtDot | worder_exp9...  |
| ResRoFSeqAtScaledDot  | rofseqatscaleddot.py  | MTRFv4RofSeqAtScaledDot | worder_exp9...  |
| ResRoFSeqAtGen  | rofseqatgen.py  | MTRFv4RofSeqAtGen | worder_exp9...  |
| ResRoFSeqAtLoc  | rofseqatloc.py  | MTRFv4RofSeqAtLoc | worder_exp9...  |
| ResRoFSeqConv  | rofseqconv.py  | MTRFv4RofSeqConv | worder_exp9...  |

5. Continue training from last checkpoint
```
python3 main2.py MODEL_NAME DATA_FOLDER_NAME EXPERIMENT_NAME \
      --epochs NUM_EPOCHS --batch_size BATCH_SIZE --role_set Roles2Args3Mods --load_previous True
```
6. Evaluation/Testing Run
```
cd evaluation
python3 test_model.py MODEL_NAME DATA_FOLDER_NAME EXPERIMENT_NAME BATCH_SIZE True
```
