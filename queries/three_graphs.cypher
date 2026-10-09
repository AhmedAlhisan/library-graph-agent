// =====================================================================
// Milestone 5: look at the three graphs (run after extract_blurbs.py)
// =====================================================================

// A. Lexical graph: the original blurbs, in order
MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
RETURN c.chunk_id AS chunk, c.text AS text
ORDER BY c.index;

// B. Subject graph: what the LLM extracted, and from which chunk
MATCH (a:Subject_Book)-[r:SEQUEL_OF]->(b:Subject_Book)
RETURN a.name AS book, b.name AS sequel_of, r.chunk_id AS from_chunk
ORDER BY from_chunk;

// C. Provenance: trace one extracted fact back to the original sentence
MATCH (a:Subject_Book {name: 'Dunes Reborn'})-[r:SEQUEL_OF]->(b:Subject_Book)
MATCH (c:Chunk {chunk_id: r.chunk_id})
RETURN a.name AS book, b.name AS sequel_of, c.text AS evidence;

// D. The domain graph is untouched: still 2 trusted SEQUEL_OF
MATCH (:Book)-[r:SEQUEL_OF]->(:Book)
RETURN count(r) AS domain_sequels;

// E. All extracted book names: spot the same book written two ways
MATCH (s:Subject_Book)
RETURN s.name AS name
ORDER BY name;

// F. All three layers as a picture
MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)<-[:EXTRACTED_FROM]-(s:Subject_Book)
RETURN d, c, s;
