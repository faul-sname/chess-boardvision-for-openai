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

1. Introduce the `init standard` command, which sets the chessboard to the standard opening. This command always returns `ok`.
2. Introduce the `get <square>` command, which dumps out the content of a given square (e.g. "empty" or "white pawn" or "black knight").
3. Introduce the `longform-move <color> <piece> from <square> to <square>` command. Train it only on valid moves for now. This command always returns `ok`. In order to fine-tune it, I will train on prompts of the form `init standard > ok / get E2 > white pawn / get E4 > empty / move white pawn from E2 to E4 > ok / get E2 > empty / get E4 > white pawn`.
4. Test how the model does, at this point, on sequences that look like `init standard / move white pawn from E2 to E4 / move black pawn from E7 to E5 / move white pawn from D2 to D3 / get (D[2-7]|E[2-7])`. If it does poorly here, fine-tune further on this type of sequence until the model groks this structure.
5. Introduce the `whose-turn` command. It will return `white` or `black` depending on whose turn it is, switching every time a move is made.
6. Introduce the idea of an illegal move by having a player move when it is not their turn. The model will, instead of returning `ok`, return `illegal: not your turn`.
7. Add in illegal moves where the player tries to move a piece that is not in the starting position
8. Add in illegal moves where the player tries to move through or into an occupied space without capturing
9. Add in illegal moves where the player tries to capture their own piece, or capture illegally
10. Give examples of normal legal and illegal moves and captures for all the piece types
11. Teach about en passant, castling, pawn promotion, etc.
12. Teach about check, stalemate, and checkmate
13. Introduce commands in the format `e3 # longform-move white pawn from E2 to E3`
14. Start adding in fine-tune pairs with and without the `# longform-move white pawn from E2 to E3`, or with garbage after the `#`, to teach the model that only the first bit is important.
15. Introduce a "versus mode" command, which suppresses any `ok` messages, and changes the prompt from `$` to `[player]` or `[computer]`
16. Fine-tune a whole bunch on real games, with a few examples thrown in where the player makes an illegal move, and no examples where the computer makes an illegal move
17. Fine-tune to remove prefix junk
