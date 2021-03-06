from fastcore.basics import store_attr
from fastcore.meta import delegates

from fastai_minima.callback.core import Callback, CancelBatchException

from transformers import PreTrainedModel

class GatherInputsCallback(Callback):
    """
    Prepares basic input dictionary for HuggingFace Transformers

    This `Callback` generates a very basic dictionary consisting of `input_ids`,
    `attention_masks`, and `token_type_ids`, and saves it to the attribute `self.learn.inputs`.

    If further data is expected or needed from the batch, the additional Callback(s) should have
    an order of -2
    """
    order = -3

    def before_validate(self):
        """
        Sets the number of inputs in `self.dls`
        """
        x = self.dl.one_batch()
        self.learn.dls.n_inp = len(x)

    def before_batch(self):
        """
        Turns `self.xb` from a tuple to a dictionary of either
            `{"input_ids", "attention_masks", "token_type_ids"}`d
        or
            `{"input_ids", "attention_masks"}`
        """
        inputs = {
                "input_ids":self.learn.xb[0],
                "attention_mask":self.learn.xb[1]
        }

        if len(self.learn.xb) > 2:
            inputs["token_type_ids"] = self.learn.xb[2]

        self.learn.inputs = inputs
        
class SetInputsCallback(Callback):
    """
    Callback which runs after `GatherInputsCallback` that sets `self.learn.xb`
    """
    order = -1

    def __init__(self, as_dict=False): store_attr()

    def before_batch(self):
        """
        Set `self.learn.xb` to `self.learn.inputs.values()`
        """
        if not self.as_dict:
            self.learn.xb = list(self.learn.inputs.values())
        else:
            self.learn.xb = self.learn.inputs

class GeneratorCallback(Callback):
    """
    Callback used for models that utilize `self.model.generate`
    """
    
    @delegates(PreTrainedModel.generate)
    def __init__(self, num_beams:int, min_length:int, max_length:int, early_stopping:bool, **kwargs):
        store_attr()
        self.kwargs = kwargs
    
    def before_batch(self):
        """
        Run model-specific inference
        """
        
        pred = self.learn.model.generate(
            input_ids = self.xb['input_ids'],
            attention_mask = self.xb['attention_mask'],
            num_beams = self.num_beams,
            min_length = self.min_length,
            max_length = self.max_length,
            early_stopping = self.early_stopping,
            **self.kwargs
        )
        
        self.learn.pred = pred
        
        raise CancelBatchException # skip original model inference