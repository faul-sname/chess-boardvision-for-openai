import json
import math
import os
import sqlite3
import dotenv
import openai
import random
import time

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
RANKS, FILES = "87654321", "ABCDEFGH"
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

def create_finetune_stage_1_dataset(n):
    board = get_standard_starting_board()
    dataset = []
    for i in range(n):
        lines = []
        lines.append('$ init standard')
        lines.append('> ok')
        for j in range(random.randint(1, 4)):
            square = random.choice(FILES) + random.choice(RANKS)
            lines.append(f'$ get {square}')
            if board[square] is None:
                lines.append('> empty')
            else:
                lines.append('> ' + ' '.join(board[square]))
        dataset.append({
            'prompt': '\n'.join(lines[:-1]) + '\n>',
            'completion': lines[-1][1:],
        })
    return dataset

def do_finetune(dataset, name, parent_model):
    input_filename = f'./artifacts/finetune-inputs/{name}.jsonl'
    output_filename = f'./artifacts/finetune-outputs/{name}.json'
    with open(input_filename, 'w') as f:
        for row in dataset:
            f.write(json.dumps(row) + "\n")
        f.close()
    upload_response = openai.File.create(file=open(input_filename, 'rb'), purpose='fine-tune')
    file_id = upload_response.id
    fine_tune_response = openai.FineTune.create(training_file=file_id, model='babbage')
    while fine_tune_response.status in ['pending', 'running']:
        print(f"Fine-tune {name} is {fine_tune_response.status}")
        time.sleep(15)
        fine_tune_response.refresh()
    if fine_tune_response.status != 'succeeded':
        raise Exception(f"Unexpected status {fine_tune_response.status}")
    with open(output_filename, 'w') as f:
        f.write(json.dumps({
            'name': name,
            'parent_model': parent_model,
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
    """
    >>> dataset = create_finetune_stage_1_dataset(1000)
    >>> ft_stage_1 = do_finetune(dataset, 'teach-chess-standard-position', 'babbage')
    >>> score_finetune_stage_1('babbage')
    -640.0
    >>> score_finetune_stage_1('babbage:ft-personal-2023-02-19-07-40-09')
    -0.000534477
    """
