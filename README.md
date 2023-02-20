## The goal:

A language model where the interaction looks like

```
[player] c4
[computer] e5
[player] g3
[computer] nf6
[player] bg2
[computer] d5
[player] bh1
Illegal move: h1 is occupied
[player] bxh1
Illegal move: cannot capture a piece of your own color
[player] cxd5
[computer] Nxd5
```

## The tentative plan:

The step in **bold** is the one I am currently working on.

1. Introduce the `init standard` command, which sets the chessboard to the standard opening. This command always returns `ok`.
2. Introduce the `init empty` command, which sets the chessboard to empty. This command always returns `ok`. The idea here is to teach the model that a square can contain different things depending on earlier context.
3. Introduce the `print square <square>` command, which dumps out the content of a given square (e.g. "empty" or "white pawn" or "black knight").
4. Introduce the `print active color` command, which prints "black" or "white" depending on whose turn it is.
5. Introduce the `detailed move <color> <piece> from <square> to <square>` command.
    * Train it only on valid moves for now.
    * This command always returns `ok`.
    * Initially, always show that command in the context of
        * `$ init standard > ok`
        * `$ print square E2 > white pawn`
        * `$ print square E4 > empty`
        * `$ print active color > white`
        * `$ detailed move white pawn from E2 to E4 > ok`
        * `$ print square E2 > empty`
        * `$ print square E4 > white pawn`
        * `$ print active color > black`
6. **Slowly wean the model off of the surrounding context for the `detailed move` commands -- do this by slowly dropping the probability of each of the 6 surrounding commands from 1 to 0.2**
7. **Test how the model does, at this point, on sequences that look like `init standard / move white pawn from E2 to E4 / move black pawn from E7 to E5 / move white pawn from D2 to D3 / get (D[2-7]|E[2-7])`. If it does poorly here, fine-tune further on this type of sequence until the model groks this structure.**
8. Introduce the `whose-turn` command. It will return `white` or `black` depending on whose turn it is, switching every time a move is made.
9. Introduce the idea of an illegal move by having a player move when it is not their turn. The model will, instead of returning `ok`, return `illegal: not your turn`.
10. Add in illegal moves where the player tries to move a piece that is not in the starting position
11. Add in illegal moves where the player tries to move through or into an occupied space without capturing
12. Add in illegal moves where the player tries to capture their own piece, or capture illegally
13. Give examples of normal legal and illegal moves and captures for all the piece types
14. Teach about en passant, castling, pawn promotion, etc.
15. Teach about check, stalemate, and checkmate
16. Introduce commands in the format `e3 # longform-move white pawn from E2 to E3`
17. Start adding in fine-tune pairs with and without the `# longform-move white pawn from E2 to E3`, or with garbage after the `#`, to teach the model that only the first bit is important.
18. Introduce a "versus mode" command, which suppresses any `ok` messages, and changes the prompt from `$` to `[player]` or `[computer]`
19. Fine-tune a whole bunch on real games, with a few examples thrown in where the player makes an illegal move, and no examples where the computer makes an illegal move
20. Fine-tune to remove prefix junk

## Updates as of 2023-02-20

After the introduction of the `detailed move` command, interaction with the model looks like

```
$ init standard
> ok (99.65%)
$ show active color
> white
$ show a2
> white pawn (95.15%)
$ show a4
> empty (100.0%)
$ detailed move white pawn from a2 to a4
> ok (99.51%)
$ show a2
> empty (68.96%)
$ show a4
> white pawn (100.0%)
$ show active color
> black (71.14%)
```

The model seems to be struggling a little bit to pick up the idea that contents of a square can change, and that the active player toggles after each move. However, so far I think this is more of a problem of slow learning than a problem of not having the capacity to learn this at all.

Update: after 5 more fine-tune rounds with increasing amounts of dropout, the output is looking a lot better:

Starting from the prefix of
```
$ init standard
> ok (99.78%)
$ detailed move white pawn from a2 to a4
> ok (99.93%)
```
* the command `print square a2` now says `empty` with 99.35% confidence
* the command `print square a4` now says `white pawn` with 99.99% confidence
* the command `print active color` now says `black` with 97.32% confidence
* performance remains very good (99%+) on `print *` commands that occur _before_ any `detailed move` commands

Starting with the somewhat more complex prefix of
```
$ init standard
> ok
$ detailed move white pawn from d2 to d4
> ok
$ detailed move black pawn from d7 to d5
> ok
$ detailed move white pawn from e2 to e3
> ok
$ detailed move black pawn from c7 to c6
> ok
```

I observe

* `print active color` => `white` (94.59%)
* `print square d2` => `empty` (86.83%)
* `print square d3` => `empty` (99.80%)
* `print square d4` => `white pawn` (96.70%)
* `print square c7` => `empty` (99.78%)
* `print square c6` => `black pawn` (99.98%)

so it really does look to me like the model has grokked the concept of "pawns can move".

Additionally of potential interest:
```
$ detailed move white knight from b1 to c3
> ok
$ print square b1
> empty (83.87%)
$ print square c3
> white pawn (86.21%) | white knight (12.95%)
```
Right now the model seems to think that the thing in the destination square is always a pawn (which is reasonable, it's never seen anything else), but even without any training at all it has a slight suspicion that the content of the destination square is instead the content of the source square.

