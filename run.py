import os
import argparse

def read_data(datapath):
    """Reads data from files in datapath directory"""
    with open(os.path.join(datapath, 'questions.txt'), 'r') as f_in:
        inputs = [line.strip() for line in f_in]
    
    with open(os.path.join(datapath, 'reference_answers.txt'), 'r') as f_ref:
        refsol = [line.strip() for line in f_ref]
    
    return inputs, refsol

def forward(inputs):
    """Forward function, to be implemented"""
    raise NotImplementedError
    
def loss(outputs, refsol):
    """Loss function, to be implemented"""
    raise NotImplementedError

# Skeleton code from Llama3.2
def main(args):
    inputs, refsol = read_data(args.data_path)

    outputs = forward(inputs)

    with open(os.path.join(args.data_path, 'system_output.txt'), 'w') as f_out:
        for output in outputs:
            f_out.write(output + '\n')

    if args.loss:
        loss(outputs, refsol)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-path', default='./data')
    parser.add_argument('-L','--loss', action='store_true')
    args = parser.parse_args()
    main(args)
