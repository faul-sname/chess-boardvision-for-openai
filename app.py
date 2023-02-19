import json
import os
import sqlite3
import dotenv
import openai
import random

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

    $ set board to standard starting position
    > ok
    $ get FR # where F is the file A-H and R is the rank 1-8
    > (nothing|(white|black) (pawn|rook|knight|bishop|queen|king))
"""

if __name__ == '__main__':
    dotenv.load_dotenv()
    openai.api_key = os.getenv('OPENAI_API_KEY')
