from typing import Union, List
from pathlib import Path
from abc import ABC, abstractmethod

from flair.data import Sentence

import torch
from torch import nn
from torch.utils.data import TensorDataset, DataLoader

from fastcore.basics import noop, store_attr, patch, first
from fastcore.meta import delegates

from fastai_minima.callback.core import Callback, GatherPredsCallback
from fastai_minima.callback.training_utils import CudaCallback, ProgressCallback

from fastai_minima.learner import Learner, DataLoaders

from adaptnlp.callback import GatherInputsCallback, SetInputsCallback

@patch
def one_batch(self:DataLoader):
    """
    Grabs one batch of data from the `DataLoader` and deletes the iter
    """
    res = first(self)
    if hasattr(self, 'it'): delattr(self, 'it')
    return res

@patch
def after_validate(self:GatherPredsCallback):
    "noop"
    pass

class _NoopModel(nn.Module):
    """
    Very basic model that performs y = mx+b. Is used only as a placeholder model for `BaseLearner`.
    Is based on https://github.com/fastai/fastai/blob/master/fastai/test_utils.py#L30
    """
    def __init__(self):
        super().__init__()
        self.a,self.b = nn.Parameter(torch.randn(1)),nn.Parameter(torch.randn(1))

    def forward(self, x): return x*self.a + self.b
    
class _BaseLearner:
    """
    Simple `Learner` class with `synth` DataLoaders, a noop model, and a noop loss function.

    Contains access to minimal `Learner` functionality including:
      - `get_preds`
      - `lr_find`, `fit_one_cycle`, `fit_flat_cos`, `fit_sgdr`, `fit` (not implemented)
      - `metrics`, `opt_func`, `splitter`, `wd`, `moms` (not implemented)
    """
    __cbs = [CudaCallback(), SetInputsCallback(), GatherInputsCallback()]

    def __init__(self) -> None:
        """
        Generates blank `Learner` and stores it away privately.
        """
        self.__learner = Learner(self._generate_dls(), _NoopModel(), loss_func=noop, cbs=self.__cbs)
        self.__default_dls, self.__default_model = True, True

    def _generate_dls(self, a=2, b=3, batch_size=16, n_train=10, n_valid=2) -> DataLoaders:
        """
        Builds synthetic `DataLoaders`.
        Implementation based on https://github.com/fastai/fastai/blob/master/fastai/test_utils.py#L18
        """
        def get_data(n) -> TensorDataset:
            """
            Generates synthetic `TensorDataset`
            """
            x = torch.randn(batch_size*n, 1)
            return TensorDataset(x, a*x + b, 0.1*torch.randn(batch_size*n, 1))

        train_ds = get_data(n_train)
        valid_ds = get_data(n_valid)
        train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
        valid_dl = DataLoader(valid_ds, batch_size=batch_size, num_workers=0)
        return DataLoaders(train_dl, valid_dl)

    def get_preds(self, dl=None, cbs=[]):
        """
        Get raw predictions based on `dl` with `cbs`.

        For basic inference, `cbs` should include any `Callbacks` needed to do general inference
        """
        if dl is None: raise ValueError("`dl` should not be `None`")
        if isinstance(self.__learner.model, _NoopModel):
            raise ValueError("The default model is still set, you should override this with `_BaseLearner.set_model(x)`")
        return self.__learner.get_preds(dl=dl, cbs=cbs)

    def set_as_dict(self, as_dict:bool=False):
        """
        Sets `is_dict` in the `SetInputsCallback`. Should be utilized whenever dictating
        if the incoming batch should be a dictionary or the actual inputs.
        """
        for cb in self.__cbs:
            if isinstance(cb, SetInputsCallback):
                cb.as_dict = as_dict

    def set_model(self, model):
        """
        Sets `Learner`'s model to `model`
        """
        self.__learner.model = model


class AdaptiveModel(ABC):
    _learn = _BaseLearner()
    
    def set_model(self, model):
        """ Sets model in `_learn` """
        self._learn.set_model(model)
        self.model = model
        
    def set_as_dict(self, as_dict:bool=False):
        """ Sets `as_dict` in `_learn` """
        self._learn.set_as_dict(as_dict)

    def get_preds(self, dl=None, cbs=[]):
        """
        Get raw predictions based on `dl` with `cbs`.

        For basic inference, `cbs` should include any `Callbacks` needed to do general inference
        """
        return self._learn.get_preds(dl=dl, cbs=cbs)
        
    @abstractmethod
    def load(
        self,
        model_name_or_path: Union[str, Path],
    ):
        """ Load model into the `AdaptiveModel` object as alternative constructor """
        raise NotImplementedError("Please Implement this method")

    @abstractmethod
    def predict(
        self,
        text: Union[List[Sentence], Sentence, List[str], str],
        mini_batch_size: int = 32,
        **kwargs,
    ) -> List[Sentence]:
        """ Run inference on the model """
        raise NotImplementedError("Please Implement this method")

    @abstractmethod
    def train(
        self,
    ) -> None:
        """ Evaluate on the model """
        raise NotImplementedError("Please Implement this method")

    @abstractmethod
    def evaluate(
        self,
    ) -> None:
        """ Evaluate on the model """
        raise NotImplementedError("Please Implement this method")
