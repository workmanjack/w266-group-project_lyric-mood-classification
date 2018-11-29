# project imports
from utils import read_file_contents, configure_logging, logger
from scrape_lyrics import LYRICS_TXT_DIR


# python and package imports
from tensorflow.contrib.tensorboard.plugins import projector
from sklearn.manifold import TSNE
import tensorflow as tf
import pandas as pd
import numpy as np
import collections
import pickle
import string
import random
import time
import math
import os


# workaround for strange _tinker3 import error in matplotlib that didn't occur in jupyter notebook
# https://stackoverflow.com/questions/47778550/need-tkinter-on-my-python-3-6-installation-windows-10
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt


VOCAB_SIZE = 50000
UNKNOWN_TAG = 'UNK'
LOGS_TF_DIR = 'logs/tf'
LYRICS2VEC_DIR = os.path.join(LOGS_TF_DIR, 'lyrics2vec_expanded')
VOCABULARY_FILE = os.path.join(LYRICS2VEC_DIR, 'vocabulary.txt')
LYRICS2VEC_DATA_PICKLE = os.path.join(LYRICS2VEC_DIR, 'lyrics2vec_data.pickle')
LYRICS2VEC_COUNT_PICKLE = os.path.join(LYRICS2VEC_DIR, 'lyrics2vec_count.pickle')
LYRICS2VEC_DICT_PICKLE = os.path.join(LYRICS2VEC_DIR, 'lyrics2vec_dict.pickle')
LYRICS2VEC_REVDICT_PICKLE = os.path.join(LYRICS2VEC_DIR, 'lyrics2vec_revdict.pickle')
LYRICS2VEC_EMBEDDINGS_PICKLE = os.path.join(LYRICS2VEC_DIR, 'lyrics2vec_embeddings.pickle')


class lyrics2vec(object):
    """
    thank you: https://github.com/tensorflow/tensorflow/blob/master/tensorflow/examples/tutorials/word2vec/word2vec_basic.py
    """
    
    def __init__(self):
        self.data_index = 0
        return
    
    @classmethod
    def InitFromLyrics(lyrics_root, preprocessing_func, words_file=VOCABULARY_FILE):
        LyricsVectorizer = lyrics2vec()
        # only extract words if we absolutely need to as it takes ~5 minutes
        # first look for pickled datasets
        datasets_loaded = LyricsVectorizer.load_datasets()
        if not datasets_loaded:
            words = LyricsVectorizer.extract_words(lyrics_root, preprocessing_func, words_file=words_file)
            LyricsVectorizer.build_dataset(VOCAB_SIZE, words)
            LyricsVectorizer.save_datasets()
        return LyricsVectorizer
  
    def extract_words(self, preprocessing_func, root_dir=LYRICS_TXT_DIR, words_file=VOCABULARY_FILE):
        """
        Iterates over all files in <root_dir>, reads contents, applies
        <preprocessing_func> on text, and returns a python list of all words
        
        Args:
          preprocessing_func: function, function to tokenize and possibly perform more ops to text
          root_dir: str, root dir of lyrics (default: LYRICS_TXT_DIR)
          words_file: str, path to vocabulary file (default: VOCABULARY_FILE)
        """
        start = time.time()

        words = list()
        if words_file and os.path.exists(words_file):
            logger.info('Words file already exists at {0}'.format(words_file))
            logger.info('Words will be read from words file to save time.')
            with open(words_file, 'r', encoding='utf-8') as f:
                for line in f:
                    words.append(line.replace('\n', ''))
        else:
            if words_file:
                logger.warning('Provided words file path "{0}" does not exist. Using {1} instead.'.format(words_file, VOCABULARY_FILE))
                words_file = VOCABULARY_FILE
            else:
                logger.info('No word_file provided. Creating new word file at {0}.'.format(VOCABULARY_FILE))
                words_file = VOCABULARY_FILE
            lyricfiles = os.listdir(root_dir)
            num_files = len(lyricfiles)
            contents_processed = 0
            for count, lyricfile in enumerate(lyricfiles):
                lyricfile = os.path.join(root_dir, lyricfile)
                if count % 10000 == 0:
                    logger.debug('{0}/{1} lyric files processed. {2:.02f} minutes elapsed. {3} contents processed. {4} words acquired.'.format(
                        count, num_files, (time.time() - start) / 60, contents_processed, len(words)))
                contents = read_file_contents(lyricfile)
                if contents and contents[0]:
                    tokens = preprocessing_func(contents[0])
                    words += tokens
                    #songs.append(tokens)
                    contents_processed += 1

            logger.info('Saving words to file {0}'.format(words_file))
            with open(words_file, 'w', encoding='utf-8') as f:
                for word in words:
                    f.write(word + '\n')

        logger.info('{0} words found'.format(len(words)))
        logger.info('First {0} words:\n{1}'.format(10, words[:10]))

        logger.info('Elapsed Time: {0} minutes.'.format((time.time() - start) / 60))

        return words
    
    def build_dataset(self, n_words, words):
        """
        Process raw inputs into a dataset.
        
        Args:
          n_words: int, number of words to retain IDs for
          words: list of str, raw inputs
        
        Initializes the following class data members:
        * count: dict, maps each unique token to its int num of occurences in the dataset
        * dictionary: dict, maps each token to its int id
        * reversed_dictionary: dict, maps each int id to its token
        * data: list, int ids in order for all tokens in dataset
        
        Returns: None
        """
        self.count = [[UNKNOWN_TAG, -1]]
        self.count.extend(collections.Counter(words).most_common(n_words - 1))
        self.dictionary = dict()
        for word, _ in self.count:
            self.dictionary[word] = len(self.dictionary)
        self.data = list()
        unk_count = 0
        for word in words:
            if word in self.dictionary:
                index = self.dictionary[word]
            else:
                index = 0  # dictionary[UNKNOWN_TAG]
                unk_count += 1
            self.data.append(index)
        self.count[0][1] = unk_count
        self.reversed_dictionary = dict(zip(self.dictionary.values(), self.dictionary.keys()))
        return
    
    def transform(self, lyrics):
        """
        Maps each word in provided array to its integer ID from the constructed vocabulary
        
        Args:
          lyrics: list of strs
        
        Returns: list of ints
        """
        lyric_ids = list()
        for word in lyrics:
            lyric_ids.append(self.dictionary.get(word, 0))
            #print('{0} -> {1}'.format(word, lyric_ids[-1]))
        return lyric_ids

    def load_datasets(self):
        loaded = False
        if os.path.exists(LYRICS2VEC_DATA_PICKLE):
            self.data = unpicklify(LYRICS2VEC_DATA_PICKLE)
            self.count = unpicklify(LYRICS2VEC_COUNT_PICKLE)
            self.dictionary = unpicklify(LYRICS2VEC_DICT_PICKLE)
            self.reversed_dictionary = unpicklify(LYRICS2VEC_REVDICT_PICKLE)
            loaded = True
            logger.info('datasets successfully loaded via pickle')
        else:
            logger.info('cannot load datasets! no pickle data files found')
        return loaded
    
    def save_datasets(self):
        picklify(self.data, LYRICS2VEC_DATA_PICKLE)
        picklify(self.count, LYRICS2VEC_COUNT_PICKLE)
        picklify(self.dictionary, LYRICS2VEC_DICT_PICKLE)
        picklify(self.reversed_dictionary, LYRICS2VEC_REVDICT_PICKLE)
        logger.info('datasets successfully pickled')
        return
    
    def _generate_batch(self, data, batch_size, num_skips, skip_window):
        assert batch_size % num_skips == 0
        assert num_skips <= 2 * skip_window
        batch = np.ndarray(shape=(batch_size), dtype=np.int32)
        context = np.ndarray(shape=(batch_size, 1), dtype=np.int32)
        span = 2 * skip_window + 1  # [ skip_window input_word skip_window ]
        buffer = collections.deque(maxlen=span)
        for _ in range(span):
            buffer.append(data[self.data_index])
            self.data_index = (self.data_index + 1) % len(data)
        for i in range(batch_size // num_skips):
            target = skip_window  # input word at the center of the buffer
            targets_to_avoid = [skip_window]
            for j in range(num_skips):
                while target in targets_to_avoid:
                    target = random.randint(0, span - 1)
                targets_to_avoid.append(target)
                batch[i * num_skips + j] = buffer[skip_window]  # this is the input word
                context[i * num_skips + j, 0] = buffer[target]  # these are the context words
            buffer.append(data[self.data_index])
            self.data_index = (self.data_index + 1) % len(data)
        # Backtrack a little bit to avoid skipping words in the end of a batch
        self.data_index = (self.data_index + len(data) - span) % len(data)
        return batch, context

    def train(self, V=50000, batch_size=128, embedding_size=128, skip_window=4, num_skips=2, num_sampled=64):
        """
        Step 4: Build and train a skip-gram model.
        """
        
        #batch_size = 128
        #embedding_size = 128  # Dimension of the embedding vector.
        #skip_window = 1  # How many words to consider left and right.
        #skip_window = 4
        #num_skips = 2  # How many times to reuse an input to generate a label.
        #num_sampled = 64  # Number of negative examples to sample.
        
        logger.info('Building lyrics2vec graph')
        logger.info('V={0}, batch_size={1}, embedding_size={2}, skip_window={3}, num_skips={4}, num_sampled={4}'.format(
            V, batch_size, embedding_size, skip_window, num_skips, num_sampled))
        data_index = 0  # reset data_index for batch generation
        
        # We pick a random validation set to sample nearest neighbors. Here we limit the
        # validation samples to the words that have a low numeric ID, which by
        # construction are also the most frequent. These 3 variables are used only for
        # displaying model accuracy, they don't affect calculation.
        valid_size = 16  # Random set of words to evaluate similarity on.
        valid_window = 100  # Only pick dev samples in the head of the distribution.
        valid_examples = np.random.choice(valid_window, valid_size, replace=False)

        graph = tf.Graph()

        with graph.as_default():

            # Input data.
            with tf.name_scope('inputs'):
                train_inputs = tf.placeholder(tf.int32, shape=[batch_size])
                train_labels = tf.placeholder(tf.int32, shape=[batch_size, 1])
                valid_dataset = tf.constant(valid_examples, dtype=tf.int32)

            # Ops and variables pinned to the CPU because of missing GPU implementation
            with tf.device('/cpu:0'):
                # Look up embeddings for inputs.
                with tf.name_scope('embeddings'):
                    embeddings = tf.Variable(
                        tf.random_uniform([V, embedding_size], -1.0, 1.0))
                    embed = tf.nn.embedding_lookup(embeddings, train_inputs)

            # Construct the variables for the NCE loss
            with tf.name_scope('weights'):
                nce_weights = tf.Variable(
                    tf.truncated_normal(
                        [V, embedding_size],
                        stddev=1.0 / math.sqrt(embedding_size)))
            with tf.name_scope('biases'):
                nce_biases = tf.Variable(tf.zeros([V]))

            # Compute the average NCE loss for the batch.
            # tf.nce_loss automatically draws a new sample of the negative labels each
            # time we evaluate the loss.
            # Explanation of the meaning of NCE loss:
            #   http://mccormickml.com/2016/04/19/word2vec-tutorial-the-skip-gram-model/
            with tf.name_scope('loss'):
                loss = tf.reduce_mean(
                    tf.nn.nce_loss(
                        weights=nce_weights,
                        biases=nce_biases,
                        labels=train_labels,
                        inputs=embed,
                        num_sampled=num_sampled,
                        num_classes=V))

            # Add the loss value as a scalar to summary.
            tf.summary.scalar('loss', loss)

            # Construct the SGD optimizer using a learning rate of 1.0.
            with tf.name_scope('optimizer'):
                optimizer = tf.train.GradientDescentOptimizer(1.0).minimize(loss)

            # Compute the cosine similarity between minibatch examples and all embeddings.
            norm = tf.sqrt(tf.reduce_sum(tf.square(embeddings), 1, keepdims=True))
            normalized_embeddings = embeddings / norm
            valid_embeddings = tf.nn.embedding_lookup(normalized_embeddings,
                                                    valid_dataset)
            similarity = tf.matmul(
                valid_embeddings, normalized_embeddings, transpose_b=True)

            # Merge all summaries.
            merged = tf.summary.merge_all()

            # Add variable initializer.
            init = tf.global_variables_initializer()

            # Create a saver.
            saver = tf.train.Saver()

        logger.info('Beginning graph training')
        start = time.time()

        num_steps = 100001

        with tf.Session(graph=graph) as session:
            # Open a writer to write summaries.
            writer = tf.summary.FileWriter(LYRICS2VEC_DIR, session.graph)

            # We must initialize all variables before we use them.
            init.run()
            logger.info('Initialized')

            average_loss = 0
            for step in range(num_steps):
                batch_inputs, batch_labels = self._generate_batch(self.data, batch_size, num_skips, skip_window)
                feed_dict = {train_inputs: batch_inputs, train_labels: batch_labels}

                # Define metadata variable.
                run_metadata = tf.RunMetadata()

                # We perform one update step by evaluating the optimizer op (including it
                # in the list of returned values for session.run()
                # Also, evaluate the merged op to get all summaries from the returned "summary" variable.
                # Feed metadata variable to session for visualizing the graph in TensorBoard.
                _, summary, loss_val = session.run(
                    [optimizer, merged, loss],
                    feed_dict=feed_dict,
                    run_metadata=run_metadata)
                average_loss += loss_val

                # Add returned summaries to writer in each step.
                writer.add_summary(summary, step)
                # Add metadata to visualize the graph for the last run.
                if step == (num_steps - 1):
                    writer.add_run_metadata(run_metadata, 'step%d' % step)

                if step % 2000 == 0:
                    if step > 0:
                        average_loss /= 2000
                    # The average loss is an estimate of the loss over the last 2000 batches.
                    logger.debug('Average loss at step {0}: {1}'.format(step, average_loss))
                    logger.debug('Time Elapsed: {0} minutes'.format((time.time() - start) / 60))
                    average_loss = 0

                # Note that this is expensive (~20% slowdown if computed every 500 steps)
                if step % 10000 == 0:
                    sim = similarity.eval()
                    for i in range(valid_size):
                        valid_word = self.reversed_dictionary[valid_examples[i]]
                        top_k = 8  # number of nearest neighbors
                        nearest = (-sim[i, :]).argsort()[1:top_k + 1]
                        log_str = 'Nearest to {0}:'.format(valid_word)
                        for k in range(top_k):
                            close_word = self.reversed_dictionary[nearest[k]]
                            log_str = '{0} {1},'.format(log_str, close_word)
                        logger.debug(log_str)

            self.final_embeddings = normalized_embeddings.eval()

            # Write corresponding labels for the embeddings.
            with open(LYRICS2VEC_DIR + '/metadata.tsv', 'w') as f:
                for i in range(V):
                    f.write(self.reversed_dictionary[i] + '\n')

            # Save the model for checkpoints.
            saver.save(session, os.path.join(LYRICS2VEC_DIR, 'model.ckpt'))

            # Create a configuration for visualizing embeddings with the labels in TensorBoard.
            config = projector.ProjectorConfig()
            embedding_conf = config.embeddings.add()
            embedding_conf.tensor_name = embeddings.name
            embedding_conf.metadata_path = os.path.join(LYRICS2VEC_DIR, 'metadata.tsv')
            projector.visualize_embeddings(writer, config)

        writer.close()

        logger.info('Time Elapsed: {0} minutes'.format((time.time() - start) / 60))
        
        return
    
    def save_embeddings(self, dest=LYRICS2VEC_EMBEDDINGS_PICKLE):
        picklify(self.final_embeddings, dest)
        return
    
    def load_embeddings(self, src=LYRICS2VEC_EMBEDDINGS_PICKLE):
        loaded = False
        if os.path.exists(LYRICS2VEC_EMBEDDINGS_PICKLE):
            self.final_embeddings = unpicklify(LYRICS2VEC_EMBEDDINGS_PICKLE)
            loaded = True
        else:
            logger.info('cannot load final embeddings! no pickle data file found')
        return loaded

    def plot_with_labels(self, filename):
        """
        Function to draw visualization of distance between embeddings.
        """
        
        logger.info('Beginning label plotting')
        start = time.time()
        
        tsne = TSNE(perplexity=30, n_components=2, init='pca', n_iter=5000, method='exact')
        plot_only = 500
        low_dim_embs = tsne.fit_transform(self.final_embeddings[:plot_only, :])
        labels = [self.reversed_dictionary[i] for i in range(plot_only)]

        assert low_dim_embs.shape[0] >= len(labels), 'More labels than embeddings'
        plt.figure(figsize=(18, 18))  # in inches
        for i, label in enumerate(labels):
            x, y = low_dim_embs[i, :]
            plt.scatter(x, y)
            plt.annotate(
                label,
                xy=(x, y),
                xytext=(5, 2),
                textcoords='offset points',
                ha='right',
                va='bottom')

            plt.savefig(filename)
        
        logger.info('Elapsed Time: {0}'.format((time.time() - start) / 60))
        logger.info('saved plot at {0}'.format(filename))

    def __repr__(self):
        return '<lyrics2vec()>'.format()


def main():

    prep_nltk()
    configure_logging(logname='lyrics2vec')
    
    lyrics_vectorizer = lyrics2vec()
    # only extract words if we absolutely need to as it takes ~5 minutes
    datasets_loaded = False
    # first look for pickled datasets
    #datasets_loaded = lyrics_vectorizer.load_datasets()
    if not datasets_loaded:
        df = build_labeled_lyrics_dataset('data/labeled_lyrics_expanded.csv')
        return
        words = extract_words(df.lyrics)
        words = lyrics_vectorizer.extract_words(LYRICS_TXT_DIR, lyrics_preprocessing, words_file=VOCABULARY_FILE)
        lyrics_vectorizer.build_dataset(VOCAB_SIZE, words)
        lyrics_vectorizer.save_datasets()

    embeddings_loaded = False
    # only train embeddings if we absolutely need to as it takes a while!
    #embeddings_loaded = lyrics_vectorizer.load_embeddings()
    if not embeddings_loaded:
        lyrics_vectorizer.train(V=V)
        lyrics_vectorizer.save_embeddings()

    lyrics_vectorizer.plot_with_labels(os.path.join(LYRICS2VEC_DIR, 'embeddings_expanded.png'))
    
    return
    
    ### Batch Demo
    
    #batch_size = len(os.listdir(LYRICS_TXT_DIR))  # rough approximation of appropriate number of batches
    #batch_size = batch_size - 1 if batch_size % 2 != 0 else batch_size
    batch_size = 8
    print('batch_size =', batch_size)
    num_skips = 2  # How many times to reuse an input to generate a label.
    skip_window = 4  # take 4 before and 4 after for context window

    batch, labels = generate_batch(data, batch_size=batch_size, num_skips=num_skips, skip_window=skip_window)
    for i in range(batch_size):
        print(batch[i], reverse_dictionary[batch[i]], '->', labels[i, 0],
            reverse_dictionary[labels[i, 0]])
    print(data_index)
    print(batch)
    print(len(labels))
    
    return


if __name__ == '__main__':
    main()
    