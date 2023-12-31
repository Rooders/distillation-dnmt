from itertools import chain
import gc
import glob
import codecs
import numpy as np
from collections import defaultdict
import pprint
import torch
import torchtext.data
from utils.logging import logger
import onmt.constants as Constants
from tkinter import _flatten
def _getstate(self):
  return dict(self.__dict__, stoi=dict(self.stoi))


def _setstate(self, state):
  self.__dict__.update(state)
  self.stoi = defaultdict(lambda: 0, self.stoi)

torchtext.vocab.Vocab.__getstate__ = _getstate
torchtext.vocab.Vocab.__setstate__ = _setstate


def make_text_iterator_from_file(path):
  with codecs.open(path, "r", "utf-8") as corpus_file:
    for line in corpus_file:
      yield line

def make_features(batch, side):
  """
  Args:
      batch (Tensor): a batch of source or target data.
      side (str): for source or for target.
  Returns:
      A sequence of src/tgt tensors with optional feature tensors
      of size (len x batch).
  """
  assert side in ['src', 'tgt', 'tgt_tran', 'document_src', 'document_tgt']
  if side in batch.__dict__:
    if isinstance(batch.__dict__[side], tuple):
      data = batch.__dict__[side][0]
    else:
      data = batch.__dict__[side]
  else:
    return None

  return data

def save_fields_to_vocab(fields):
  """
  Save Vocab objects in Field objects to `vocab.pt` file.
  """
  vocab = []
  for k, f in fields.items():
    if f is not None and 'vocab' in f.__dict__:
      f.vocab.stoi = f.vocab.stoi
      vocab.append((k, f.vocab))
  return vocab

def get_source_fields(fields=None, sentence_level=False, use_auto_trans=False):
  if fields is None:
    fields = {}

  if sentence_level:
    fields["src"] = torchtext.data.Field(
      init_token=Constants.SLU_WORD,
      pad_token=Constants.PAD_WORD,
      eos_token=Constants.EOS_WORD,
      include_lengths=True)
  else:
    nested_field = torchtext.data.Field(
      init_token=Constants.SLU_WORD,
      eos_token=Constants.EOS_WORD,
      pad_token=Constants.PAD_WORD
    )

    fields["src"] = torchtext.data.NestedField(
      nested_field,
      include_lengths=True,
      pad_token=Constants.PAD_WORD)

  fields["indices"] = torchtext.data.Field(
      use_vocab=False, dtype=torch.long,
      sequential=False)

  return fields

def get_auto_trans_fields(fields=None, sentence_level=False, use_auto_trans=False):
  if fields is None:
    fields = {}

  if sentence_level:
    fields["tgt_tran"] = torchtext.data.Field(
      init_token=Constants.SLU_WORD,
      pad_token=Constants.PAD_WORD,
      eos_token=Constants.EOS_WORD,
      include_lengths=False)
  else:
    nested_field = torchtext.data.Field(
      init_token=Constants.SLU_WORD,
      eos_token=Constants.EOS_WORD,
      pad_token=Constants.PAD_WORD
    )

    fields["tgt_tran"] = torchtext.data.NestedField(
      nested_field,
      include_lengths=False,
      pad_token=Constants.PAD_WORD)
    
  fields["indices"] = torchtext.data.Field(
      use_vocab=False, dtype=torch.long,
      sequential=False)
  
  return fields

def get_target_fields(fields=None, sentence_level=False):
  if fields is None:
    fields = {}
  if sentence_level:
    fields["tgt"] = torchtext.data.Field(
      init_token=Constants.BOS_WORD,
      eos_token=Constants.EOS_WORD,
      pad_token=Constants.PAD_WORD)
  else:
    nested_filed = torchtext.data.Field(
      init_token=Constants.BOS_WORD,
      eos_token=Constants.EOS_WORD,
      pad_token=Constants.PAD_WORD)

    fields["tgt"] = torchtext.data.NestedField(
      nested_filed,
      pad_token=Constants.PAD_WORD)

  fields["indices"] = torchtext.data.Field(
    use_vocab=False, dtype=torch.long,
    sequential=False)

  return fields


def get_fields(sentence_level=True, use_auto_trans=False):
  fields = {}
    
  fields = get_source_fields(fields, sentence_level)
  fields = get_target_fields(fields, sentence_level)
  if use_auto_trans:
    fields = get_auto_trans_fields(fields, sentence_level)

  return fields

def load_fields_from_vocab(vocab, opt, tgt_tran=None):
  """
  Load Field objects from `vocab.pt` file.
  """
  vocab = dict(vocab)
  if tgt_tran:
    use_trans=True
  else:
    use_trans=opt.use_auto_trans
  fields = get_fields(opt.sentence_level, use_auto_trans=use_trans)
  for k, v in vocab.items():
    # Hack. Can't pickle defaultdict :(
    v.stoi = defaultdict(lambda: 0, v.stoi)
    # if k == 'context' or k == 'tgt_encoder': 
    #   # may use pre-trained model from context-opennmt
    #   pass
    # else:
    fields[k].vocab = v
  if use_trans:
    fields['tgt_tran'].vocab = vocab['tgt']

  # if opt.sentence_level:
  #   fields['src'].vocab = fields['src'].vocab
  #   fields['tgt'].vocab = fields['tgt'].vocab
  # else:
  if not opt.sentence_level:
    fields['tgt'].nesting_field.vocab = fields['tgt'].vocab
    fields['src'].nesting_field.vocab = fields['src'].vocab
    if use_trans:
      fields['tgt_tran'].nesting_field.vocab = fields['tgt_tran'].vocab
  
  return fields

def load_fields(opt, checkpoint):
  if checkpoint is not None:
    logger.info('Loading vocab from checkpoint at %s.' % opt.train_from)
    fields = load_fields_from_vocab(checkpoint['vocab'], opt)
    # if opt.paired_trans and fields['tgt'].vocab.__contains__(Constants.SEG_WORD)==False:
    #   fields['tgt'].vocab.append_token(Constants.SEG_WORD)
         
  else:
    fields = load_fields_from_vocab(torch.load(opt.data + '_vocab.pt'), opt)

  if opt.use_auto_trans:
    logger.info(' * vocabulary size. source = %d; target = %d; auto_target = %d' %
              (len(fields['src'].vocab), len(fields['tgt'].vocab), len(fields['tgt'].vocab)))
  else:
    logger.info(' * vocabulary size. source = %d; target = %d' %
              (len(fields['src'].vocab), len(fields['tgt'].vocab)))
  # if opt.sentence_level:
  #   fields['tgt'].vocab = fields['tgt'].vocab
  #   fields['src'].vocab = fields['src'].vocab
  # else:
  #   fields['tgt'].nesting_field.vocab = fields['tgt'].vocab
  #   fields['src'].nesting_field.vocab = fields['src'].vocab
  
  return fields

class DatasetIter(object):
  """ An Ordered Dataset Iterator, supporting multiple datasets,
      and lazy loading.

  Args:
      datsets (list): a list of datasets, which are lazily loaded.
      fields (dict): fields dict for the datasets.
      batch_size (int): batch size.
      batch_size_fn: custom batch process function.
      device: the GPU device.
      is_train (bool): train or valid?
  """

  def __init__(self, datasets, fields, batch_size, batch_size_fn,
               device, is_train):
    self.datasets = datasets
    self.fields = fields
    self.batch_size = batch_size
    self.batch_size_fn = batch_size_fn
    self.device = device
    self.is_train = is_train
    self.cur_iter = self._next_dataset_iterator(datasets)
    # We have at least one dataset.
    assert self.cur_iter is not None

  def __iter__(self):
    dataset_iter = (d for d in self.datasets)
    while self.cur_iter is not None:
      for batch in self.cur_iter:
        yield batch
      self.cur_iter = self._next_dataset_iterator(dataset_iter)

  def __len__(self):
    # We return the len of cur_dataset, otherwise we need to load
    # all datasets to determine the real len, which loses the benefit
    # of lazy loading.
    assert self.cur_iter is not None
    return len(self.cur_iter)

  def _next_dataset_iterator(self, dataset_iter):
    try:
      # Drop the current dataset for decreasing memory
      if hasattr(self, "cur_dataset"):
        self.cur_dataset.examples = None
        gc.collect()
        del self.cur_dataset
        gc.collect()

      self.cur_dataset = next(dataset_iter)
    except StopIteration:
      return None

    # We clear `fields` when saving, restore when loading.
    self.cur_dataset.fields = self.fields

    # Sort batch by decreasing lengths of sentence required by pytorch.
    # sort=False means "Use dataset's sortkey instead of iterator's".
    return OrderedIterator(
      dataset=self.cur_dataset, batch_size=self.batch_size,
      batch_size_fn=self.batch_size_fn,
      device=self.device, train=self.is_train,
      sort=False, sort_within_batch=True,
      repeat=False)
    
class OrderedIterator(torchtext.data.Iterator):
  """ Ordered Iterator Class """

  def create_batches(self):
    """ Create batches """
    if self.train:
      def _pool(data, random_shuffler):
        for p in torchtext.data.batch(data, self.batch_size * 100):
          p_batch = torchtext.data.batch(
            sorted(p, key=self.sort_key),
            self.batch_size, self.batch_size_fn)
          for b in random_shuffler(list(p_batch)):

            yield b

      self.batches = _pool(self.data(), self.random_shuffler)
    else:
      self.batches = []
      for b in torchtext.data.batch(self.data(), self.batch_size,
                                    self.batch_size_fn):

        self.batches.append(sorted(b, key=self.sort_key))



def load_dataset(corpus_type, opt):
  assert corpus_type in ["train", "valid"]

  def _dataset_loader(pt_file, corpus_type):
    dataset = torch.load(pt_file)
    logger.info('Loading %s dataset from %s, number of examples: %d' %
                (corpus_type, pt_file, len(dataset)))
    return dataset

  # Sort the glob output by file name (by increasing indexes).
  pts = sorted(glob.glob(opt.data + '_' + corpus_type + '.[0-9]*.pt'))
  if pts:
    for pt in pts:
      yield _dataset_loader(pt, corpus_type)
  else:
    pt = opt.data + '_' + corpus_type + '.pt'
    yield _dataset_loader(pt, corpus_type)

def build_dataset(fields,
                  src_data_iter,
                  tgt_data_iter,
                  auto_trans_iter,
                  src_seq_length=0, tgt_seq_length=0,
                  src_seq_length_trunc=0, tgt_seq_length_trunc=0,
                  sentence_level=True,
                  use_filter_pred=True, pre_paired_trans=False):
  assert src_data_iter != None
  src_examples_iter = Dataset.make_examples(src_data_iter, src_seq_length_trunc, 'src', sentence_level)
  
  if tgt_data_iter != None:
    tgt_examples_iter = Dataset.make_examples(tgt_data_iter, tgt_seq_length_trunc, 'tgt', sentence_level, pre_paired_trans)
  else:
    tgt_examples_iter = None
  
  if auto_trans_iter != None:
    auto_trans_examples_iter = Dataset.make_examples(auto_trans_iter, tgt_seq_length_trunc, 'tgt_tran', sentence_level, pre_paired_trans)
  else:
    auto_trans_examples_iter = None
  
  dataset = Dataset(fields, src_examples_iter, tgt_examples_iter, auto_trans_examples_iter,
                        src_seq_length=src_seq_length,
                        tgt_seq_length=tgt_seq_length,
                        sentence_level=sentence_level,
                        use_filter_pred=use_filter_pred)

  return dataset


def build_dataset_iter(datasets, fields, opt, is_train=True):
  """
  This returns user-defined train/validate data iterator for the trainer
  to iterate over. We implement simple ordered iterator strategy here,
  but more sophisticated strategy like curriculum learning is ok too.
  """
  batch_size = opt.batch_size if is_train else opt.valid_batch_size
  sentence_level = opt.sentence_level
  
  if is_train and opt.batch_type == "tokens":
    if sentence_level:
      def batch_size_fn(new, count, sofar):
        """
        In token batching scheme, the number of sequences is limited
        such that the total number of src/tgt tokens (including padding)
        in a batch <= batch_size
        """
        # Maintains the longest src and tgt length in the current batch
        global max_src_in_batch, max_tgt_in_batch
        # Reset current longest length at a new batch (count=1)
        if count == 1:
            max_src_in_batch = 0
            max_tgt_in_batch = 0
        # Src: <bos> w1 ... wN <eos>
        max_src_in_batch = max(max_src_in_batch, len(new.src) + 2)
        # Tgt: w1 ... wN <eos>
        max_tgt_in_batch = max(max_tgt_in_batch, len(new.tgt) + 1)
        src_elements = count * max_src_in_batch
        tgt_elements = count * max_tgt_in_batch
        return max(src_elements, tgt_elements)
    else:
      def batch_size_fn(new, count, sofar):
        """
        In token batching scheme, the number of sequences is limited
        such that the total number of src/tgt tokens (including padding)
        in a batch <= batch_size
        """
        # Maintains the longest src and tgt length in the current batch
        global max_src_in_batch, max_tgt_in_batch, max_sent_num_in_batch, max_src_seq_len, max_tgt_seq_len
        # Reset current longest length at a new batch (count=1)
        if count == 1:
            max_src_in_batch = 0
            max_tgt_in_batch = 0
            max_sent_num_in_batch = 0
            max_src_seq_len = 0
            max_tgt_seq_len = 0
            
        # Src: w1 ... wN <eos>
        # num_src_token = 0
        max_sent_num_in_batch = max(max_sent_num_in_batch, len(new.src))
        
        for sent in new.src:
          max_src_seq_len = max(max_src_seq_len, len(sent) + 1)
        max_src_in_batch = max(max_src_in_batch, max_sent_num_in_batch * max_src_seq_len)
        
        for sent in new.tgt:
          max_tgt_seq_len = max(max_tgt_seq_len, len(sent) + 2)
        max_tgt_in_batch = max(max_tgt_in_batch, max_sent_num_in_batch * max_tgt_seq_len)
        # Tgt:<bos> w1 ... wN <eos>
        # max_tgt_in_batch = max(max_tgt_in_batch, num_tgt_token)
        # max_sent_num_in_batch = max(max_sent_num_in_batch, num_sent)
        src_elements = count * max_src_in_batch
        tgt_elements = count * max_tgt_in_batch
        return max(src_elements, tgt_elements)
  else:
    batch_size_fn = None

  if opt.gpu_ranks:
    device = "cuda"
  else:
    device = "cpu"

  return DatasetIter(datasets, fields, batch_size, batch_size_fn,
                         device, is_train)


class Dataset(torchtext.data.Dataset):
  def __init__(self, fields, src_examples_iter, tgt_examples_iter, auto_trans_examples_iter,
               src_seq_length=0, tgt_seq_length=0,
               sentence_level=False,
               use_filter_pred=True):

    self.src_vocabs = []
    
    def _join_dicts(*args):
      return dict(chain(*[d.items() for d in args]))

    out_fields = get_source_fields(sentence_level=sentence_level)
    if tgt_examples_iter is not None and auto_trans_examples_iter is not None:
      # print("3")
      examples_iter = (_join_dicts(src, tgt, auto_trans) for src, tgt, auto_trans in
                        zip(src_examples_iter, tgt_examples_iter, auto_trans_examples_iter))
      out_fields = get_target_fields(out_fields, sentence_level)
      out_fields = get_auto_trans_fields(out_fields, sentence_level)
    
    elif tgt_examples_iter is not None and auto_trans_examples_iter is None:
      # print("2")
      examples_iter = (_join_dicts(src, tgt) for src, tgt in
                        zip(src_examples_iter, tgt_examples_iter))
      out_fields = get_target_fields(out_fields, sentence_level)
    
    elif tgt_examples_iter is None and auto_trans_examples_iter is not None:
      # print("1")
      examples_iter = (_join_dicts(src, auto_tran) for src, auto_tran in
                        zip(src_examples_iter, auto_trans_examples_iter))
      out_fields = get_auto_trans_fields(out_fields, sentence_level)
    
    else:
      examples_iter = src_examples_iter
      
    keys = out_fields.keys()
    out_fields = [(k, fields[k]) for k in keys]
    example_values = ([ex[k] for k in keys] for ex in examples_iter)

    out_examples = []
    for ex_values in example_values:
      example = torchtext.data.Example()
      for (name, field), val in zip(out_fields, ex_values):
        if field is not None:
          setattr(example, name, field.preprocess(val))
        else:
          setattr(example, name, val)
      #print(out_fields)
      #print(ex_values)
      out_examples.append(example)

    def filter_pred(example):
      """ ? """
      if sentence_level is True:
        return 0 < len(example.src) <= src_seq_length \
          and 0 < len(example.tgt) <= tgt_seq_length
          
      return True

    filter_pred = filter_pred if use_filter_pred else lambda x: True

    super(Dataset, self).__init__(
        out_examples, out_fields, filter_pred
    )
  def __getstate__(self):
    return self.__dict__

  def __setstate__(self, _d):
    self.__dict__.update(_d)
    
  def sort_key(self, ex):
    if hasattr(ex, "tgt"):
      return len(ex.src), len(ex.tgt)
    return len(ex.src)
    
  @staticmethod
  def make_examples(text_iter, truncate, side, sentence_level=False, paired_trans=False, seg_tok=Constants.SEG_WORD):
    assert side in ('src', 'tgt', 'tgt_tran')
    if sentence_level:
      for i, line in enumerate(text_iter):
        words = line.strip().split()
        if truncate:
          words = words[:truncate]
        example_dict = {side: tuple(words), "indices": i}
        yield example_dict
    else:
      for i, doc_line in enumerate(text_iter):
        sentences = doc_line.split(' ||| ')  #[sents_num]
        # add the placeholder for the blank sentence.
        sentences = [Constants.PAD_WORD if sent.strip() == "" else sent.strip() for sent in sentences]
        # #if side == 'tgt' and paired_trans:
        # if paired_trans:
        #   sentence_pairs = []
        #   first_pair = sentences[-1] + " " + seg_tok + " " + sentences[0]
        #   sentence_pairs.append(first_pair)
        #   for sent1, sent2 in zip(sentences[:-1], sentences[1:]):
        #     paired_sent = sent1 + " " + seg_tok + " " + sent2 
        #     sentence_pairs.append(paired_sent)
        #   assert len(sentence_pairs) == len(sentences)
        #   words = [p.strip().split() for p in sentence_pairs]
          
        # else:    
        words = [p.strip().split() for p in sentences]  #[sent_num, seq_len]
        # print(sentences)
        
        assert(" " not in sentences or "" not in sentences)
        if truncate:
          words = (w[:truncate] for w in words)
        example_dict = {side: tuple(words), "indices": i}
        yield example_dict
    
