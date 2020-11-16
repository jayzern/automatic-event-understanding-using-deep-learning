----------------------------------------------------------------------------------------------------------------------------------------------
## Team2 Setup (Python3 and TF2.3)
1. Pull code from github and arrange into the following directory
#### File arrangements
* All files should be organized in following structure. model and results folder should be initially empty if we are trainining models.
```
├── data
    ├── exp9_0.01-16-16-Roles2Args3Mods-NoFrAn-v1
    ├── ....    
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
    │   ├── nnrf.py
    │   ├── nnrf_mt.py
    │   ├── rofa.py
    │   ├── resrofa.py
    │   ├── rofa_st.py
    │   └── resrofa_st.py
    │   └── rofawd.py
    │   └── rofbeg.py
    │   └── rofdense.py
    ├── evaluation
    │   ├── __init__.py
    │   └── ...
    └── README.md
```
2. Install dependencies (TensorFlow 2.3, Numpy)
3. Download NLTK for evaluation by doing
```
import nltk
nltk.download('all')
```
4. move into directory of main2.py file
```
cd event-embedding
```
4. Choose which models to run
a. ResRofa (baseline)
```
python3 main2.py MTRFv4Res exp9_0.01-16-16-Roles2Args3Mods-NoFrAn-v1 20200717-batch1024-iters25 --epochs 25 --batch_size 1024 --role_set Roles2Args3Mods
```
b. RofWD
```
python3 main2.py MTRFv4WD exp9_0.01-16-16-Roles2Args3Mods-NoFrAn-v1 20200717-batch1024-iters25 --epochs 25 --batch_size 1024 --role_set Roles2Args3Mods
```
c. RofBeg
```
python3 main2.py MTRFv4RofBeg exp9_0.01-16-16-Roles2Args3Mods-NoFrAn-v1 20200717-batch1024-iters25 --epochs 25 --batch_size 1024 --role_set Roles2Args3Mods
```
d. ResDense
```
python3 main2.py MTRFv4ResDense exp9_0.001-16-16-Roles2Args3Mods-NoFrAn-v1 20200717-batch1024-iters25 --epochs 25 --batch_size 1024 --role_set Roles2Args3Mods
```
5. Continue training
```
python3 main2.py MTRFv4Res exp9_0.01-16-16-Roles2Args3Mods-NoFrAn-v1 20200717-batch1024-iters25 --epochs 25 --batch_size 1024 --role_set Roles2Args3Mods --load_previous True
```
6. Evaluation/Testing Run
```
cd evaluation
python3 test_model.py MTRFv4Res exp9_0.01-16-16-Roles2Args3Mods-NoFrAn-v1  20200717-batch1024-iters25  1024 True
```
