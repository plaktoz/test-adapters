# Banned words

Used by `unslop` (see `SKILL.md`, rule 8). Replace each banned word or phrase with the entry in the right column. Then reread the sentence.

The file has two tables and a section on plain sense:

- **Plain language** holds words that have a shorter or clearer form.
- **Stock wording** holds words and phrases that fit any text and carry no fact.
- **Plain sense** says when a listed word stays.

Match the longest phrase first. A word also covers its other forms: "utilize" covers "utilized", and "delve" covers "delves" and "delving".

This list belongs to `unslop`. The plain-language table started as a copy of the `ste-docs` list, and the stock-wording table started as a copy of the `phrases.yaml` list of the anti-slop pack (copied 2026-11-09). Both lists are now separate from their sources. Change this file without changing the sources. Add a row when a new word needs a rule.

## Plain language

| Banned | Use instead | Reason |
|--------|-------------|--------|
| utilize, utilise | use | One word for one meaning. |
| leverage, leverages, leveraging | use, uses, using | One word for one meaning. |
| perform | do | Plain verb. |
| commence | start | Plain verb. |
| terminate | stop, end | Plain verb. |
| facilitate | help, make possible | Plain verb. |
| prior to | before | Plain word. |
| subsequent to | after | Plain word. |
| in order to | to | Shorter form. |
| in the event that | if | Plain word. |
| due to the fact that | because | Plain word. |
| given that | because | Plain word. |
| at this point in time | now | Plain word. |
| a number of | several, or the number | Exact meaning. |
| a lot of | many | Exact meaning. |
| in addition | also | Plain word. |
| as well as | and | Plain word. |
| in spite of | although | Plain word. |
| whether or not | whether | Shorter form. |
| via | through, by | Plain word. |
| may | can (ability), is allowed to (permission) | One meaning for each word. |
| ensure | make sure | Plain verb. |
| i.e. | that is | Plain words. |
| and/or | two sentences, one for each case | One meaning per sentence. |
| etc. | (delete, and list all items) | Exact list. |
| simply | (delete) | Adds no meaning. |
| just | (delete) | Adds no meaning. |
| easily | (delete) | Adds no meaning. |
| obviously | (delete) | Adds no meaning. |
| don't | do not | No contractions. |
| can't | cannot | No contractions. |
| won't | will not | No contractions. |
| isn't | is not | No contractions. |
| it's | it is | No contractions. |

## Stock wording

Each entry here carries no fact. Use the fix in the right column. If the fix says to name something and the text holds nothing to name, delete the phrase when the sentence keeps every fact it had. If the sentence loses a fact, keep the sentence and tell the author what is missing. Do not invent the fact.

| Banned | Use instead | Reason |
|--------|-------------|--------|
| in today's rapidly evolving | (delete, and start with the point) | Fits any text. |
| leverage the power of | use | Plain verb. |
| seamlessly integrate | integrate, and name the method | A claim with no detail. |
| robust framework | framework, and name the property | A claim with no detail. |
| comprehensive solution | solution, and name what it covers | A claim with no detail. |
| delve into | examine | Plain verb. |
| serves as | is | Plain verb. |
| cutting-edge | (delete, or name the technique) | A claim with no detail. |
| empower teams to, empowers teams to | let teams | Plain verb. |
| designed to address the fundamental challenges | solves, and name the problem | A claim with no detail. |
| cohesive platform | platform | Adds no meaning. |
| at scale | (delete, or give the size) | A claim with no number. |
| faces several challenges | (name each challenge) | A claim with no detail. |
| increasing maintenance burden | (name the cost) | A claim with no detail. |
| broader challenge of coordinating | (name the problem) | A claim with no detail. |
| delve, delves, delving | examine, examines, examining | Plain verb. |
| pivotal | important, and say why | A claim with no detail. |
| underscore, underscores | show, shows | Plain verb. |
| tapestry | (delete, and name the parts) | Adds no meaning. |
| landscape | (delete, or name the field) | Adds no meaning. |
| robust | (delete, or name the property) | A claim with no detail. |
| seamlessly | (delete) | Adds no meaning. |
| multifaceted | (delete, or list the facets) | A claim with no detail. |

## Plain sense

A listed word stays when it names the thing itself and not the stock use. Ask one question: is the sentence about that thing? If yes, keep the word.

- "A landscape photo" is about page or photo shape. Keep `landscape`. "The AI landscape" is stock use. Replace it.
- "Meet in May" names a month. Keep `May`. "It may fail" asks for `can` or `is allowed to`.
- "A just ruling" means fair. Keep `just`. "It just works" adds no meaning. Delete `just`.
- "The leverage ratio of a firm" is a finance term. Keep `leverage`. "Leverage the cache" asks for `use`.

Also keep a listed word that is part of a name, a quoted text, a code identifier, a path or a command (for example `terminate` as a function name, or the title of a book). When you are unsure, keep the word and do not mention it.
