import json
import math
import os
import sqlite3
import sys
import dotenv
import openai
import random
import time
from lib.chess_program import ChessProgram, RANKS, FILES

"""
The general plan is to have a fine-tuned LM learn to simulate a user's
interaction with a CLI chess program.

User input lines begin with $, while output lines begin with >
Each input line contains $, a command with some number of arguments,
and optionally a comment which starts with # and continues to the
end of the line.
Each output line contains > then a couple of tokens

In the first training stage, we will teach the LM what a chess board
in the standard starting position looks like. To do this, we will need
to introduce the following two commands:

    $ init standard # set chess board to standard starting position
    > ok
    $ get FR # where F is the file A-H and R is the rank 1-8
    > (empty|(white|black) (pawn|rook|knight|bishop|queen|king))
"""
STANDARD_BACK_RANK_ORDER = ['rook', 'knight', 'bishop', 'queen', 'king', 'bishop', 'knight', 'rook']

def get_empty_board():
    return { f + r: None for r in RANKS for f in FILES }

def get_standard_starting_board():
    back_rank = dict(zip(FILES, STANDARD_BACK_RANK_ORDER))
    return {
        f + r: (
            'black' if r in "87" else 'white',
            back_rank.get(f) if r in "18" else 'pawn'
        ) if r in "8721" else None
        for r in RANKS
        for f in FILES
    }

def init_program(state):
    state['program'] = ChessProgram()

def run_command(command):
    def f(state):
        state['program'].handle_command(command)
    return f

def print_random_square():
    def f(state):
        state['program'].handle_command('print square ' + random_square())
    return f

def random_square():
    return random.choice(FILES) + random.choice(RANKS)

def noop(state):
    return

def move_random_pawn(show):
    def f(state):
        program = state['program']
        moves = []
        color, piece = program.active_color, 'pawn'
        forward = program.get_forward_direction(color)
        for src_square, content in program.board.items():
            if content == (color, piece):
                for dy in (forward, forward*2):
                    x, y = program.square_to_xy(src_square)
                    dst_square = program.xy_to_square((x,y+dy))
                    try:
                        program.assert_legal_move(color, piece, src_square, dst_square)
                        moves.append((color, piece, src_square, dst_square))
                    except:
                        pass
        if len(moves) == 0:
            return
        move = random.choice(moves)
        color, piece, src_square, dst_square = move
        if random.random() < show.get('print_turn_before_prob', 0):
            program.handle_command(f'print active color')
        if random.random() < show.get('print_src_before_prob', 0):
            program.handle_command(f'print square {src_square}')
        if random.random() < show.get('print_dst_before_prob', 0):
            program.handle_command(f'print square {dst_square}')
        cmd = f'detailed move {color} {piece} from {src_square} to {dst_square}'
        program.handle_command(cmd)
        if random.random() < show.get('print_turn_after_prob', 0):
            program.handle_command(f'print active color')
        if random.random() < show.get('print_src_after_prob', 0):
            program.handle_command(f'print square {src_square}')
        if random.random() < show.get('print_dst_after_prob', 0):
            program.handle_command(f'print square {dst_square}')
    return f


STAGE_1_GRAPH = (
    {
        'START': init_program,
        'INIT_EMPTY': run_command('init empty'),
        'INIT_STANDARD': run_command('init standard'),
        'SHOW_RAND': print_random_square(),
        'SHOW_COLOR': run_command('print active color'),
        'END': noop
    },
    [
        ('START', 'INIT_STANDARD', 3),
        ('START', 'INIT_EMPTY', 1),
        ('INIT_EMPTY', 'SHOW_RAND', 1),
        ('INIT_STANDARD', 'SHOW_RAND', 4),
        ('INIT_STANDARD', 'SHOW_COLOR', 1),
        ('SHOW_RAND', 'SHOW_RAND', 7),
        ('SHOW_RAND', 'SHOW_COLOR', 1),
        ('SHOW_COLOR', 'SHOW_RAND', 1),
        ('SHOW_RAND', 'INIT_STANDARD', 1),
        ('SHOW_RAND', 'INIT_EMPTY', 1),
        ('SHOW_RAND', 'END', 2),
    ],
)

def make_stage_2_graph(helper_probs):
    return (
        {
            'START': init_program,
            'INIT_STANDARD': run_command('init standard'),
            'MOVE_RAND_PAWN': move_random_pawn(helper_probs),
            'SHOW_RAND': print_random_square(),
            'SHOW_COLOR': run_command('print active color'),
            'END': noop
        },
        [
            ('START', 'INIT_STANDARD', 1),
            ('INIT_STANDARD', 'SHOW_RAND', 3),
            ('INIT_STANDARD', 'MOVE_RAND_PAWN', 1),
            ('SHOW_RAND', 'SHOW_RAND', 3),
            ('SHOW_RAND', 'MOVE_RAND_PAWN', 1),
            ('SHOW_RAND', 'END', 1),
            ('MOVE_RAND_PAWN', 'SHOW_RAND', 3),
            ('MOVE_RAND_PAWN', 'MOVE_RAND_PAWN', 1),
            ('MOVE_RAND_PAWN', 'END', 1),
        ],
    )

def markov_probs(graph):
    nodes, edges = graph
    sums = {node: 0 for node in nodes}
    for src, dst, weight in edges:
        sums[src] += weight
    probs = {src: {dst: 0 for dst in nodes} for src in nodes}
    for src, dst, weight in edges:
        probs[src][dst] += weight / sums[src]
    return probs

def markov_pass(graph, start, end):
    nodes, edges = graph
    probs = markov_probs(graph)
    state = {}
    k = start
    while k != end:
        action = nodes[k]
        action(state)
        acc = 0
        r = random.random()
        for nk, np in probs[k].items():
            acc += np
            k = nk
            if acc >= r:
                break
    return state

def create_markov_dataset(graph, start, end, n, check=None):
    dataset = []
    while len(dataset) < n:
        program = markov_pass(graph, start, end)['program']
        lines = program.lines
        # program.output_prefix always ends in a space
        prompt = "".join(lines[:-1]) + program.output_prefix[:-1]
        completion = lines[-1][len(program.output_prefix)-1:]
        datapoint = {
            'prompt': prompt,
            'completion': completion
        }
        if check is not None and not check(datapoint):
            continue
        dataset.append(datapoint)
    return dataset

def run_finetune_stage1(name, base_model):
    check = lambda datapoint: len(datapoint['prompt']) <= 100
    train_dataset = create_markov_dataset(STAGE_1_GRAPH, 'START', 'END', 2**10, check)
    test_dataset = create_markov_dataset(STAGE_1_GRAPH, 'START', 'END', 2**8, check)
    return do_finetune(train_dataset, test_dataset, name, base_model)

def run_finetune_stage2(name, base_model, helper_probs):
    check = lambda datapoint: len(datapoint['prompt']) <= 700
    STAGE_2_GRAPH = make_stage_2_graph(helper_probs)
    train_dataset = create_markov_dataset(STAGE_2_GRAPH, 'START', 'END', 2**10, check)
    test_dataset = create_markov_dataset(STAGE_2_GRAPH, 'START', 'END', 2**8, check)
    return do_finetune(train_dataset, test_dataset, name, base_model)

def upload_finetune_dataset(dataset, filename):
    with open(filename, 'w') as f:
        for row in dataset:
            f.write(json.dumps(row) + "\n")
        f.close()
    upload_response = openai.File.create(file=open(filename, 'rb'), purpose='fine-tune')
    file_id = upload_response.id
    return file_id

def do_finetune(train_dataset, test_dataset, name, parent_model):
    input_train_filename = f'./artifacts/finetune-inputs/train-{name}.jsonl'
    input_test_filename = f'./artifacts/finetune-inputs/test-{name}.jsonl'
    output_filename = f'./artifacts/finetune-outputs/{name}.json'

    train_file_id = upload_finetune_dataset(train_dataset, input_train_filename)
    test_file_id = upload_finetune_dataset(test_dataset, input_test_filename)
    fine_tune_response = openai.FineTune.create(
        training_file=train_file_id,
        validation_file=test_file_id,
        model='babbage',
        suffix=name,
        batch_size=16
    )
    n_shown_events = 0
    print(f"{time.time():.3f} Fine-tune {name} created: id={fine_tune_response.id}")
    while fine_tune_response.status in ['pending', 'running']:
        print(f"{time.time():.3f} Fine-tune {name} is {fine_tune_response.status}")
        for i, event in enumerate(fine_tune_response.events):
            if i >= n_shown_events:
                print(f'   got event: {event}')
                n_shown_events += 1
        time.sleep(15)
        fine_tune_response.refresh()
    if fine_tune_response.status != 'succeeded':
        raise Exception(f"Unexpected status {fine_tune_response.status}")
    with open(output_filename, 'w') as f:
        f.write(json.dumps({
            'name': name,
            'parent_model': parent_model,
            'id': fine_tune_response.id,
            'model': fine_tune_response.fine_tuned_model,
            'events': fine_tune_response.events,
        }, indent=2))
    return fine_tune_response.fine_tuned_model

def score_top_logprobs(target_text, top_logprobs):
    """
    Unprincipled decision to say that any token that does not show at all in the top 5 logprobs
    should have a logprob of -10.

    There's probably some actually-correct math to evaluate this.
    """
    if target_text == '':
        return 0.0
    if len(top_logprobs) == 0:
        return -10.0
    opts = []
    for start, logprob in top_logprobs[0].items():
        if target_text.startswith(start):
            opts.append(logprob + score_top_logprobs(target_text[len(start):], top_logprobs[1:]))
        else:
            opts.append(-10.0)
    return max(opts)

def score_finetune_stage_1(model_name):
    '''
    Approximately the log-loss of the model with temperature=0 on every square of the
    standard chess board
    '''
    board = get_standard_starting_board()
    score = 0
    for square, content in board.items():
        prompt = "\n".join([
            "$ init standard",
            "> ok",
            f"$ get {square}",
            ">"
        ])
        prefix = " "
        suffix = "\n$"
        target_text = prefix + ("empty" if content is None else " ".join(content)) + suffix
        completion_response = openai.Completion.create(
            model=model_name,
            temperature=0,
            max_tokens=5,
            prompt=prompt,
            logprobs=5,
            stop=[suffix]
        )
        individual_score = score_top_logprobs(
            target_text,
            completion_response.choices[0].logprobs.top_logprobs
        )
        score += individual_score
        print(f'Prompt:\n{prompt}\nExpects: {target_text}\nLogprob: {individual_score}')
    return score

if __name__ == '__main__':
    dotenv.load_dotenv()
    openai.api_key = os.getenv('OPENAI_API_KEY')
    fts = []
    """
    >>> stage1_model = run_finetune_stage1('stage1-init-print', 'babbage')
    >>> stage1_model
    'babbage:ft-personal:stage1-init-print-2023-02-20-07-05-37'
    >>> stage2_model01 = run_finetune_stage2(
            'stage2-move-pawns-01',
            stage1_model,
            {
                'print_turn_before_prob': 1.0,
                'print_src_before_prob': 1.0,
                'print_dst_before_prob': 1.0,
                'print_turn_after_prob': 1.0,
                'print_src_after_prob': 1.0,
                'print_dst_after_prob': 1.0,
            }
        )
    """
    stage1_model = 'babbage:ft-personal:stage1-init-print-2023-02-20-07-05-37'
    fts.append(stage1_model)
    fts.append('babbage:ft-personal:stage2-pawn-moves-ft1-2023-02-20-09-26-50')
    for i in range(1,21):
        parent_model = fts[-1]
        prob = 5 / (i+5)
        stage2_model = run_finetune_stage2(
            f'stage2-move-pawns-{i+1:2d}',
            parent_model,
            {
                'print_turn_before_prob': prob,
                'print_src_before_prob': prob,
                'print_dst_before_prob': prob,
                'print_turn_after_prob': prob,
                'print_src_after_prob': prob,
                'print_dst_after_prob': prob,
            }
        )
        fts.append(stage2_model)
