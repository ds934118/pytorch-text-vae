import dill as pickle
import numpy as np
import os
from pathlib import Path
import time
import torch

import model
from datasets import EOS_token

def load_model(saved_vae, stored_info, cache_path, seed, device):
    stored_info = stored_info.split(os.sep)[-1]
    cache_file =  os.path.join(cache_path, stored_info)

    start_load = time.time()
    print(f"Fetching cached info at {cache_file}")
    with open(cache_file, "rb") as f:
        input_side, output_side, pairs, dataset, EMBED_SIZE, CONDITION_SIZE, DECODER_HIDDEN_SIZE, ENCODER_HIDDEN_SIZE, N_ENCODER_LAYERS = pickle.load(f)
    end_load = time.time()
    print(f"Cache {cache_file} loaded (load time: {end_load - start_load:.2f}s)")

    if os.path.exists(saved_vae):
        print(f"Found saved model {saved_vae}")
        start_load_model = time.time()

        e = model.EncoderRNN(input_side.n_words, ENCODER_HIDDEN_SIZE, EMBED_SIZE, N_ENCODER_LAYERS, bidirectional=True)
        d = model.DecoderRNN(EMBED_SIZE, CONDITION_SIZE, DECODER_HIDDEN_SIZE, input_side.n_words, 1, word_dropout=0)
        vae = model.VAE(e, d).to(device)
        vae.load_state_dict(torch.load(saved_vae))
        print(f"Trained for {vae.steps_seen} steps (load time: {time.time() - start_load_model:.2f}s)")

        print("Setting new random seed")
        if seed is None:
            # TODO: torch.manual_seed(1999) in model.py is affecting this
            new_seed = int(time.time())
            new_seed = abs(new_seed) % 4294967295 # must be between 0 and 4294967295
        else:
            new_seed = seed
        torch.manual_seed(new_seed)

        random_state = np.random.RandomState(new_seed)
        random_state.shuffle(pairs)

    return vae, input_side, output_side, pairs, dataset, EMBED_SIZE, random_state

def generate(vae, num_sample, max_length, temp, print_z, input_side, output_side, pairs, dataset, embed_size, random_state, device):
    gens = []
    zs = []
    conditions = []

    for i in range(num_sample):
        z = torch.randn(embed_size).unsqueeze(0).to(device)
        condition = model.random_training_set(pairs, input_side, output_side, random_state, device)[2]

        generated = vae.decoder.generate(z, condition, max_length, temp, device)
        generated_str = model.float_word_tensor_to_string(output_side, generated)

        EOS_str = f' {output_side.index_to_word(torch.LongTensor([EOS_token]))} '

        if generated_str.endswith(EOS_str):
            generated_str = generated_str[:-5]

        # flip it back
        generated_str = generated_str[::-1]

        print('---')
        print(dataset.decode_genres(condition))
        print(generated_str)
        gens.append(generated_str)
        zs.append(z)
        conditions.append(condition)
        if print_z:
            print(z)

    return gens, zs, conditions

def run(saved_vae, stored_info, cache_path=str(Path('tmp')), max_length=50, num_sample=10, seed=None, temp=0.75,
            use_cuda=True, print_z=False):

    '''parser = argparse.ArgumentParser(description='pytorch-text-vae:generate')
    parser.add_argument('saved_vae', metavar='SAVED_VAE', help='saved PyTorch vae model')
    parser.add_argument('stored_info', metavar='STORED_INFO', help='pkl of stored info')
    parser.add_argument('--cache-path', default=str(Path('tmp')), metavar='CACHE',
                        help='cache path (default: tmp)')
    parser.add_argument('--max-length', type=int, default=50, metavar='LEN',
                        help='max num words per sample (default: 50)')
    parser.add_argument('--num-sample', type=int, default=10, metavar='NS',
                        help='num samplings (default: 10)')
    parser.add_argument('--seed', type=int, default=None, metavar='S',
                        help='seed for random number generator (default: None)')
    parser.add_argument('--temp', type=float, default=0.75, metavar='T',
                        help='sample temperature (default: 0.75)')

    cuda_parser = parser.add_mutually_exclusive_group(required=False)
    cuda_parser.add_argument('--cuda', dest='use_cuda', action='store_true')
    cuda_parser.add_argument('--no-cuda', dest='use_cuda', action='store_false')

    prn_z_parser = parser.add_mutually_exclusive_group(required=False)
    prn_z_parser.add_argument('--print-z', dest='print_z', action='store_true')
    prn_z_parser.add_argument('--no-print-z', dest='print_z', action='store_false')

    parser.set_defaults(use_cuda=True, print_z=False)

    args = parser.parse_args()

    args_passed = locals()['args']
    print(args_passed)'''
    args_passed = locals()
    print(args_passed)

    DEVICE = torch.device(f'cuda:{torch.cuda.current_device()}' if torch.cuda.is_available() and use_cuda else 'cpu')

    vae, input_side, output_side, pairs, dataset, embed_size, random_state = load_model(saved_vae, stored_info, cache_path, seed, DEVICE)
    gens, zs, conditions = generate(vae, num_sample, max_length, temp, print_z, input_side, output_side, pairs, dataset, embed_size, random_state, DEVICE)

if __name__ == "__main__":
    import fire; fire.Fire(run)
