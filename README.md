# RW-Eng-v2-beta-src

Overview (TBD)

# Recipe
## pre-process corpus:
* You can skip pre-processing if you have pre-trained models at your disposal. 
* You can also skip this process if you have preprocessed dataset(s). You will need to either edit the config file `src/event-rep/event-embedding/config.py` or map the docker container's `/root/home/data` folder (in the container's creation command line) to the location of the preprocessed files.


### annotate:
* I created a virtual env with py2.7 and dependencies (see below), and so I activate it for most stuff.
* the scripts below take two params: from-file-num  to-file-num

```
source activate py2
~/src/sem-fit/ukwac-proc/ukwac_batch_proc-3-mrft.py          1100 1499
~/src/sem-fit/ukwac-proc/ukwac_batch_proc-3-lsgnpy3.py       1100 1499 
~/src/sem-fit/ukwac-proc/ukwac_batch_proc-3-spacy.py         1100 1499
```

### merge annotations:
```
source activate py2
~/src/sem-fit/ukwac-proc/ukwac_batch_proc-3-merge-lsgnpy3.py 1100 1499
```

### preprocess DL model training+test sets:
- in each pre-processed dir (corresponding to a different set of features and/or dataset size), the file to create it is `format_datasets...py`
-  `format_datasets.py` (and variants) is now under `src/event-rep/event-embedding/format_datasets/` (previously under ~/src/sem-fit/animframe/event-embedding/) -- edit it for features and datasets before running it.

- for v1 (Tony's legacy, made compatible with v2 format), use a script such as `format_datasets_v1_exp1_0.01-4-4.py` (as opposed to `format_datasets_v2_exp1_0.01-4-4.py`)

- if using old code: remember to copy files to test/ :
   - inside docker:    /root/home/src/sem-fit/animframe/data/test/ ;
   - outside:          /home/ymarton/data/rw-eng/ukwac-proc-out-merged/test/
   - e.g.,             cp /home/ymarton/data/rw-eng/ukwac-proc-out-preproc4DL-20190929/exp1_40-4-4/* /home/ymarton/data/rw-eng
/ukwac-proc-out-merged/test/

- old pre-processed data is under /home/ymarton/data/rw-eng/ukwac-proc-out-merged/exp*


## set up env for running pre-trained models or train new models:

### Dependencies
* Python 2.7
* CUDA 7.5
* Tensorflow 0.10
* Keras 2.0
- details are under event-embedding-multitask/event-embedding/README.md

### first, get the docker image:
- Install nvidia-docker if you need it (and have GPUs) : https://github.com/NVIDIA/nvidia-docker/wiki/Installation-(version-2.0)
- then:
```
docker pull tonyhong/event-embedding:paper
```
or more recent (I think) :
```
docker pull asayeed/event-embedding
```
- follow instructions in either tonyhong or asayeed's github on installing further dependencies:

### activate docker:
#### first time activation:
- make sure first that the data folder is accessible (sometimes the folder or drive needs to be manually mounted / opened after reboot)

- if using preprocessed datasets (tabular/JSON format of fields extracted from annotated text), or preprocessing datasets outside the docker, map your preprocessed datasets folder (here assumed to be in `~$USER/data/`) to the container's data folder (`/root/home/data/`)

- note that the docker contains some old v1 version of the code, but we won't use it. Instead, map the `src` folder of this git repo to the container's src folder (`/root/home/src/`)

```
nvidia-docker run --runtime=nvidia -ti -e LANG=C.UTF-8 -v ~$USER/src/:/root/home/src/ -v ~$USER/tools/:/root/home/tools/ -v ~$USER/data/:/root/home/data/ --name semfit1 asayeed0/event-embeddings-starsem
```

- alternatively: add gpu support: see https://stackoverflow.com/questions/25185405/using-gpu-from-a-docker-container
(?) (there's probably a bug with the gpu support, so you might want to skip this alternative for now)
```
nvidia-docker run --runtime=nvidia -ti -e LANG=C.UTF-8 --gpus all  -v ~$USER/src/:/root/home/src/ -v ~$USER/tools/:/root/home/tools/ -v ~$USER/data/:/root/home/data/ --name semfitg1 asayeed0/event-embeddings-starsem
```

- Install h5py and nltk with the following command:
```
pip install h5py nltk
```
- (optional, as v2 won't use it) Install the WordNet in Python repository with:
```
$ import nltk
$ nltk.download()
 Downloader> d wordnet
```
make sure to install from python 2 (2.7). NLTK moved to python 3 so you may have to manually install an older version that supports py2.7. 

#### or, if after reboot:
```
docker start semfit1
docker attach semfit1
```

### then edit model config / code :
* /root/home/src/sem-fit/animframe/event-embedding/config.py
 (don't confuse with event-embedding-multitask/event-embedding/config.py that is not saved outside the docker)
* roles should match the pre-processing roles
* edit other params such as learning rate, ephocs, etc. Mainly set VALID_SIZE (for dev/validation set) and TEST_SIZE appropriately
* edit the model file to use the features you want, in the architecture you want, etc., under ~/src/sem-fit/animframe/event-embedding/model/ (or from within docker: /root/home/src/sem-fit/animframe/event-embedding/model/ )

### make sure GPU support exists:
* There's a bug in this step, don't worry if GPU support doesn't work for you

* in python: if "import pygpu" fails, compile+install libgpuarray as in http://deeplearning.net/software/libgpuarray/installation.html (do NOT use conda on this old docker)
```
git clone https://github.com/Theano/libgpuarray.git
cd libgpuarray
```

#### For libgpuarray:
```
cd <dir>
mkdir Build
cd Build
```
* you can pass `-DCMAKE_INSTALL_PREFIX=/path/to/somewhere` to install to an alternate location
* if static lib not found,try adding cmake flag:  `-DCMAKE_INSTALL_PREFIX=/usr/`
* if cmake not found: `apt update; apt install cmake`
* or install from the latest .sh file at https://cmake.org/download/
* also if missing: `pip2 install cython nose`

*# cmake .. -DCMAKE_BUILD_TYPE=Release # or Debug if you are investigating a crash
```
cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/
make
make install
cd ..
```

#### For pygpu:

* This must be done after libgpuarray is installed as per instructions above.
```
python setup.py build
python setup.py install
```

#### test the gpu install: (didn't work for me)
```
GPUARRAY_TEST_DEVICE="0" python -c "import pygpu;pygpu.test()"
```

## using pre-trained models
instead of training, or as a pre-step to continued training
* `mkdir src/event-rep/model` and copy the model's .h5 and \_description files there. Note that `ln -s pretrained_model_dir src/event-rep/model` will NOT work from within the docker container.

## train model:
* format: 'KERAS_BACKEND=theano python main.py NAME_OF_MODEL DATA_VERSION EXPERIMENT_VERSION ...'
* for example, model size below is 1%, and I name experiment with date+params:
```
cd src/event-rep/event-embedding

KERAS_BACKEND=theano python main2.py \
    MTRFv4Res \
    exp9_0.01-16-16-Roles2Args3Mods-NoFrAn-v1 \
    20200717-batch1024-iters25 \
    --epochs 25 --batch_size 1024 --role_set Roles2Args3Mods
```
* This format is different from the original code (Tony's)
* Optional: You might also want to try adding `THEANO_FLAGS='device=cuda,force_device=True,floatX=float32'`

### continued training
to continue training a pre-trained model, or a model of which training was interupted:
```
KERAS_BACKEND=theano python main2.py \
    MTRFv4Res \
    exp9_0.01-16-16-Roles2Args3Mods-NoFrAn-v1 \
    20200717-batch1024-iters25 \
    --epochs 25 --batch_size 1024 --role_set Roles2Args3Mods \
    --load_previous True
```

## test:
```
cd src/event-rep/event-embedding
KERAS_BACKEND=theano python evaluation/test_model.py MTRFv4Res exp9_0.01-16-16-Roles2Args3Mods-NoFrAn-v1  20200717-batch1024-iters25  1024 True
```


