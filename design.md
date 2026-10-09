# Library ontology design

How the ontology was derived: start from the questions, not from the data.

## 1. Competency questions

The questions the librarian agent must answer:

1. Which books must I read before "The Desert Star 3"?
2. Which books did a member borrow, and from which branch?
3. Who wrote this book, and what genre is it?
4. Where do the catalog system and the mobile app disagree on available copies?
5. If "The Desert Star 1" is lost, which members currently borrowing a later book in the series are affected, and at which branch?

## 2. Nouns and verbs

| Question | Nouns (candidate node types) | Verbs (candidate relationships) |
|---|---|---|
| Q1 | book | "read before" (a sequel comes after) |
| Q2 | member, book, branch | "borrow", "from" |
| Q3 | author, book, genre | "wrote", "is (genre)" |
| Q4 | catalog system, mobile app, available copies, book | "disagree on" |
| Q5 | book, member, branch, series | "lost", "borrowing", "later in the series" |

## 3. Decisions

**Node or property?**
- `Author` is a node: a book can have several authors, and an author writes many books.
- `Genre` is a node: many books share one genre, and we want to walk through it ("all books in this genre").
- `Branch` is a node: many loans happen at the same branch, and Q2 and Q5 ask "which branch".
- `title`, `isbn` are properties of `Book`: plain values that describe one book.
- "catalog system" and "mobile app" are **not** nodes. No question walks through them, so they are values of a `source` property.
- "series" is **not** a node. The sequel chain itself is the series.

**Arrow or event? (event-centric)**
- "Borrow" could be an arrow `(Member)-[:BORROWED]->(Book)`, but it has its own details (status, date, branch), and the same member can borrow the same book twice. So it becomes an event node: `Loan`.

**Context (contextual boundary)**
- A loan happens *at* a branch. `Branch` gives the loan its context.

**Two sources disagree (multiperspective)**
- One property on `Book` can hold only one number, so we would lose one system's answer. Instead, an `AvailabilityStatement` about the book holds one `Perspective` per source, each with its own `value`.

**Direction**
- Every relationship reads as a sentence from subject to object: "Author WROTE Book", "Book 3 SEQUEL_OF Book 2".

## 4. Node types

| Label | key | required |
|---|---|---|
| Book | isbn | isbn, title |
| Author | name | name |
| Genre | name | name |
| Member | member_id | member_id, name |
| Branch | name | name |
| Loan | loan_id | loan_id, status |
| AvailabilityStatement | statement_id | statement_id |
| Perspective | perspective_id | perspective_id, source, value |

`required` = what a node must have for our questions to work. A loan's date is stored too, but no question needs it, so it is optional.
`Loan` needs its own `loan_id` because the same member can borrow the same book twice.

## 5. Relationships

- (Author)-[:WROTE]->(Book)
- (Book)-[:IN_GENRE]->(Genre)
- (Book)-[:SEQUEL_OF]->(Book)
- (Member)-[:HAS_LOAN]->(Loan)
- (Loan)-[:FOR_BOOK]->(Book)
- (Loan)-[:AT_BRANCH]->(Branch)
- (AvailabilityStatement)-[:ABOUT]->(Book)
- (AvailabilityStatement)-[:ACCORDING_TO]->(Perspective)

## 6. Check: every question has a path

| Question | Path through the graph |
|---|---|
| Q1 | `(Book)-[:SEQUEL_OF*1..]->(Book)` |
| Q2 | `(Member)-[:HAS_LOAN]->(Loan)-[:FOR_BOOK]->(Book)` and `(Loan)-[:AT_BRANCH]->(Branch)` |
| Q3 | `(Author)-[:WROTE]->(Book)-[:IN_GENRE]->(Genre)` |
| Q4 | `(AvailabilityStatement)-[:ABOUT]->(Book)` and two `-[:ACCORDING_TO]->(Perspective)` |
| Q5 | `(Book 1)<-[:SEQUEL_OF*1..]-(Book)<-[:FOR_BOOK]-(Loan {status: 'borrowed'})<-[:HAS_LOAN]-(Member)` and `(Loan)-[:AT_BRANCH]->(Branch)` |

Q5 needed no new types or relationships: saturation. The count (8 node types, 8 relationships) came out of the questions; it was not chosen in advance.
