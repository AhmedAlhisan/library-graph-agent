// =====================================================================
// Milestone 4: the 5 competency questions, answered by walking paths.
// Each query is the path from design.md (section 6) turned into Cypher.
// Run them one at a time in the Neo4j Browser (http://localhost:7474).
// =====================================================================


// ---------------------------------------------------------------------
// Q1. Which books must I read before "The Desert Star 3"?   (multi-hop)
// Path: (Book)-[:SEQUEL_OF*1..]->(Book)
// ---------------------------------------------------------------------
MATCH (b:Book {title: 'The Desert Star 3'})-[:SEQUEL_OF*1..]->(prev:Book)
RETURN prev.title AS read_first, prev.year AS year
ORDER BY year;
// Expected: The Desert Star 1 (2019), The Desert Star 2 (2021)


// ---------------------------------------------------------------------
// Q2. Which books did Sara borrow, and from which branch?   (event + context)
// Path: (Member)-[:HAS_LOAN]->(Loan)-[:FOR_BOOK]->(Book), (Loan)-[:AT_BRANCH]->(Branch)
// ---------------------------------------------------------------------
MATCH (m:Member {name: 'Sara'})-[:HAS_LOAN]->(l:Loan)-[:FOR_BOOK]->(b:Book),
      (l)-[:AT_BRANCH]->(br:Branch)
RETURN b.title AS book, br.name AS branch, l.status AS status, l.date AS date
ORDER BY date;
// Expected: The Desert Star 1 | Olaya | returned | 2026-08-01
//           The Desert Star 2 | Olaya | borrowed | 2026-09-20


// ---------------------------------------------------------------------
// Q3. Who wrote "Riyadh Nights", and what genre is it?
// Path: (Author)-[:WROTE]->(Book)-[:IN_GENRE]->(Genre)
// collect() gathers several rows into one list (like GROUP BY in SQL).
// ---------------------------------------------------------------------
MATCH (a:Author)-[:WROTE]->(b:Book {title: 'Riyadh Nights'})-[:IN_GENRE]->(g:Genre)
RETURN b.title AS book, collect(a.name) AS authors, g.name AS genre;
// Expected: Riyadh Nights | [Khalid Al-Otaibi, Huda Al-Fahad] | Mystery
//           (the order inside the list may differ)


// ---------------------------------------------------------------------
// Q4. Where do the catalog and the app disagree on copies?   (multiperspective)
// Path: (AvailabilityStatement)-[:ABOUT]->(Book) + two ACCORDING_TO perspectives
// ---------------------------------------------------------------------
MATCH (s:AvailabilityStatement)-[:ABOUT]->(b:Book),
      (s)-[:ACCORDING_TO]->(cat:Perspective {source: 'catalog'}),
      (s)-[:ACCORDING_TO]->(app:Perspective {source: 'app'})
WHERE cat.value <> app.value
RETURN b.title AS book, cat.value AS catalog_says, app.value AS app_says;
// Expected: The Desert Star 3 | 1 | 0
// (The Desert Star 1 does not appear: both systems say 2.)


// ---------------------------------------------------------------------
// Q5. If "The Desert Star 1" is lost, which members currently borrowing
//     a later book in the series are affected, and at which branch?   (impact)
// Path: (Book 1)<-[:SEQUEL_OF*1..]-(later)<-[:FOR_BOOK]-(Loan)<-[:HAS_LOAN]-(Member)
// ---------------------------------------------------------------------
MATCH (lost:Book {title: 'The Desert Star 1'})<-[:SEQUEL_OF*1..]-(later:Book),
      (m:Member)-[:HAS_LOAN]->(l:Loan {status: 'borrowed'})-[:FOR_BOOK]->(later),
      (l)-[:AT_BRANCH]->(br:Branch)
RETURN m.name AS member, later.title AS book, br.name AS branch
ORDER BY member;
// Expected: Omar | The Desert Star 3 | Malaz
//           Sara | The Desert Star 2 | Olaya
// (Omar's old loan of book 1 does not appear: it is book 1 itself, and it was returned.)
