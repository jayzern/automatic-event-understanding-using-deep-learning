import os,sys
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)
import config

from .generic import GenericModel

# classname of NNRF-ST: NNRF
from .nnrf import NNRF

# classname of NNRF-MT: MTRF
from .nnrf_mt import MTRF

# classname of RoFA-MT: MTRFv4
from .rofa import MTRFv4

# classname of ResRoFA-MT: MTRFv4Res
from .resrofa import MTRFv4Res

# (TEAM2-change) classname of ResRoFDense-MT: MTRFv4ResDense
from .rofdense import MTRFv4ResDense

# (TEAM2-change) classname of RoFAWD-MT: MTRFv4WD
from .rofawd import MTRFv4WD

# (TEAM2-change) classname of RoFBeg-MT: MTRFv4RofBeg
from .rofbeg import MTRFv4RofBeg

# ablation study: sigle task version for composition methods

# classname of RoFA-ST: NNRF_ROFA
from .rofa_st import NNRF_ROFA

# classname of ResRoFA-ST: NNRF_ResROFA
from .resrofa_st import NNRF_ResROFA

# (TEAM2-change) Commeted out Yuval's model with animacy and frames
#from .resrofa_fran import MTRFwFAv1Res

# classname of RoFSeq-MT: MTRFv4RofSeqLSTM
from .rofseqlstm import MTRFv4RofSeqLSTM

# classname of RoFSeq-MT: MTRFv4RofSeqBiLSTM
from .rofseqbilstm import MTRFv4RofSeqBiLSTM

# classname of RoFSeq-MT: MTRFv4RofSeqRNN
from .rofseqrnn import MTRFv4RofSeqRNN

# classname of RoFSeq-MT: MTRFv4RofSeqBiLSTMAt
from .rofseqbilstmat import MTRFv4RofSeqBiLSTMAt

# classname of RoFSeq-MT: MTRFv4RofSeqLSTM
from .rofseqdeeplstm import MTRFv4RofSeqDeepLSTM

# classname of RoFSeq-MT: MTRFv4RofSeqLSTM
from .rofseqdeeplstmat import MTRFv4RofSeqDeepLSTMAt

# classname of RoFSeq-MT: MTRFv4RofSeqBiLSTMAt2
from .rofseqbilstmat2 import MTRFv4RofSeqBiLSTMAt2

# classname of RoFSeq-MT: MTRFv4RofSeqBiLSTMDense
from .rofseqbilstmdense import MTRFv4RofSeqBiLSTMDense

# classname of RoFSeq-MT: MTRFv4RofSeqAt
from .rofseqat import MTRFv4RofSeqAt

# classname of RoFSeq-MT: MTRFv4RofSeqAtLoc
from .rofseqatloc import MTRFv4RofSeqAtLoc

# classname of RoFSeq-MT: MTRFv4RofSeqAtDot
from .rofseqatdot import MTRFv4RofSeqAtDot

# classname of RoFSeq-MT: MTRFv4RofSeqAtScaledDot
from .rofseqatscaleddot import MTRFv4RofSeqAtScaledDot

# classname of RoFSeq-MT: MTRFv4RofSeqAtGen
from .rofseqatgen import MTRFv4RofSeqAtGen