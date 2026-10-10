// =====================================================================
// Entity resolution: crossing between the three graphs
// (run after scripts/resolve_books.py)
// =====================================================================

// A. The links: what the LLM wrote -> the official book
MATCH (s:Subject_Book)-[c:CORRESPONDS_TO]->(b:Book)
RETURN s.name AS llm_wrote, b.title AS official_title, b.isbn AS isbn, c.score AS score
ORDER BY isbn;

// B. Catalog gaps: books the LLM found that we don't have
MATCH (s:Subject_Book)
WHERE NOT (s)-[:CORRESPONDS_TO]->(:Book)
RETURN s.name AS not_in_catalog, s.best_score AS closest_score;

// C. Cross-graph walk: official book -> how the LLM wrote it -> the sentence it came from
//    domain graph -> subject graph -> lexical graph
MATCH (b:Book {title: 'The Desert Star 2'})<-[:CORRESPONDS_TO]-(s:Subject_Book)-[:EXTRACTED_FROM]->(c:Chunk)
RETURN s.name AS written_as, c.chunk_id AS chunk, c.text AS evidence;

// D. Check every LLM claim against the official data
MATCH (s1:Subject_Book)-[:SEQUEL_OF]->(s2:Subject_Book)
OPTIONAL MATCH (s1)-[:CORRESPONDS_TO]->(b1:Book)
OPTIONAL MATCH (s2)-[:CORRESPONDS_TO]->(b2:Book)
RETURN s1.name AS llm_book, s2.name AS llm_says_sequel_of,
       CASE
         WHEN b1 IS NULL OR b2 IS NULL THEN 'NEW: not in the catalog'
         WHEN EXISTS { (b1)-[:SEQUEL_OF]->(b2) } THEN 'CONFIRMED by official data'
         ELSE 'CONFLICT: official data disagrees'
       END AS verdict;
