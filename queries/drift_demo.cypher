// =====================================================================
// Break the graph on purpose, then watch the precision metric catch it
// =====================================================================

// 1. Add two FALSE relationships that are not in library.json
//    (Lina "has" Sara's loan, and Riyadh Nights becomes fantasy)
MATCH (m:Member {member_id: 'M003'}), (l:Loan {loan_id: 'L001'})
MERGE (m)-[:HAS_LOAN]->(l);

MATCH (b:Book {isbn: '978-0004'}), (g:Genre {name: 'Fantasy'})
MERGE (b)-[:IN_GENRE]->(g);

// 2. Now run:  python scripts/quality_report.py
//    Precision should drop below 95% and list both edges.

// 3. Repair: delete the two false relationships
MATCH (:Member {member_id: 'M003'})-[r:HAS_LOAN]->(:Loan {loan_id: 'L001'})
DELETE r;

MATCH (:Book {isbn: '978-0004'})-[r:IN_GENRE]->(:Genre {name: 'Fantasy'})
DELETE r;
