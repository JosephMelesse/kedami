# Like Predicate

Since its first days, SQL includes a basic form of **pattern matching on strings**. The feature is part of the WHERE clause and is triggered by the keyword LIKE. It knows two meta-characters: '_' (underscore) and '%' (percent).

```sql
SELECT * 
FROM   <table_name>
WHERE  <column_name> LIKE <like_criterion>; -- The like_criterion can contain '_' and/or '%'
```

Over time, additional functionality has been incorporated to the standard. This concerns regular expressions, which are similar to those defined by POSIX, and regular expressions as defined by the XQuery 1.0 / XPath 2.0 function fn:matches(). Finally the SQL application package ISO/IEC 13249-2:2003 Part 2: Full-Text defines methods and functions for information retrieval on fulltext.

## LIKE

The LIKE predicate compares a column of type CHAR or VARCHAR (string) with a pattern. This pattern is also a string, but it may contain two characters with a special meaning. The '_' (underscore) represents exactly one arbitrary character, and '%' (percent) represents a string of zero, one or more characters. All other characters represent themselves.

The first example retrieves all rows from table *person* with a first name starting with the two characters 'Jo', eg: 'John', 'Johanna' or 'Jonny W.'. As the meta-character '%' represents also zero characters, rows with the first name 'Jo' are also retrieved.

```sql
SELECT * 
FROM   person
WHERE  firstname LIKE 'Jo%';
```

The next example retrieves all rows from table *person* with a last name similar to 'Meier', eg: 'Meyer' or 'Maier'. The two underscores represents exactly two (arbitrary) characters. Consider, that there may be unexpected results like 'Miler' (but not 'Miller').

```sql
SELECT * 
FROM   person
WHERE  lastname LIKE 'M__er';
```

The definition of the two meta-characters '_' and '%' implies a problem: What if one wants to search for these characters itself? The solution is the same as in other programming languages: one defines an escape mechanism to mask the meta-characters and prefix the meta-character in the pattern by this escape character. In SQL the syntax is:

```sql
...
WHERE <column_name> LIKE <like_criterion> ESCAPE <escape_character>;
```

```sql
-- Retrieve one of the meta-characters: 'Electric_Motor' but not 'Electric Motor'
SELECT * 
FROM   parts
WHERE  partname LIKE 'Electric\_Motor' ESCAPE '\';
```

```sql
-- Retrieve the escape character itself: 'Electric\Motor' but not 'Electric Motor'
SELECT * 
FROM   parts
WHERE  partname LIKE 'Electric\\Motor' ESCAPE '\';
```

The escape character can be any character; it is not limited to the backslash, eg.: ... ESCAPE '!'

## POSIX Semantic

In an outdated version of the SQL standard, there was the keyword SIMILAR, which introduced a pattern match in the sense of POSIX. Nowadays, it is deprecated.

Some implementations offer pattern matching in this sense, but use arbitrary keywords like REGEXP, REGEXP_MATCHES, REGEXP_LIKE or operators like '~' to activate the feature.

## XQuery Semantic

The SQL standard defines the keyword LIKE_REGEX to activate pattern matching as defined by the XQuery 1.0 / XPath 2.0 function fn:matches().

## Full-Text

The SQL standard is complemented by *ISO/IEC 13249 SQL Multimedia and Application Packages*. Part 2 *Full-Text* defines routines and methods for information retrieval in text documents. It deals with objects like: word, phrase, sentence, and paragraph. There are special constructs; to search for words or phrases, search words within a definable distance, thesaurus features like broader terms of a word, soundex-similarity, ranking of results, and much more. The central method of these features is CONTAINS.

```sql
-- Retrieve rows with 'word_1' and 'word_2' (in this order) within a sequence of 10 words.
SELECT * 
FROM   t1
WHERE  CONTAINS(' "word_1" NEAR "word_2" WITHIN 10 WORDS IN ORDER ') = 1;
```

Such features are far beyond pattern matching - but it is the natural next step. SQL implementations offer them mostly in combination with special text indexes.
