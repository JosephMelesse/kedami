# Recursions

Sometimes the rows of **one** table are structured in such a way that they represent a hierarchy or a network **within** this table. Typical use cases are management structures, bill of materials (a machine consists of several smaller machines, …), or network structures (e.g.: flight plans).

To retrieve particular rows and all rows that correlate to them, one can use set operations in combination with subqueries to merge them together to one result set. But this technique is limited as one must exactly know the number of levels. Apart from the fact that the number of levels changes from case to case, the subselect syntax differs from level to level. To overcome these restrictions, SQL offers a syntax to express queries in a **recursive** manner. They retrieve the rows of all affected levels, independent from their number.

## Syntax

The SQL standard uses a special form of its `WITH clause`, which is explained on the  previous page, to define recursive queries. The clause occurs before a SELECT, INSERT, UPDATE, or DELETE keyword and is part of the appropriate command.

Hint: The `WITH clause` (with or without the 'RECURSIVE' key word) is often referred to as a 'common table expression (CTE)'.

Hint: Oracle supports the syntax of the SQL standard since version 11.2. MySQL 8.0 supports the RECURSIVE keyword. Earlier MySQL versions do not support recursions at all and recommend procedural workarounds.

```sql
-- The command starts with a 'with clause', which contains the optional 'RECURSIVE' key word.
WITH [RECURSIVE] intermediate_table (temp_column_name [,...]) AS 
  (SELECT ... FROM real_table          -- initial query to a real table                          (1)
     UNION ALL                                                                                   (3)
   SELECT ... FROM intermediate_table  -- repetitive query using the intermediate table          (2)
  )
-- The 'with clause' is part of a regular SELECT.
-- This SELECT refers to the final result of the 'with clause'.                                  (4)
SELECT ... FROM intermediate_table
; -- consider the semicolon: the command runs from the 'WITH' up to here.
```

The evaluation sequence is as follows:
1. The initial query to a real table or a view is executed and creates the start point for step 2.
1. Usually, the repetitive query consists of a join between the real table or view and the result set build up so far. This step is repeated until no new rows are found.
1. The result sets from step 1. and 2. are merged together.
1. The final SELECT acts on the result of step 3.

## Example Table

To demonstrate recursive queries, we define an example table. It holds information about persons and their ancestors. Because ancestors are always persons, everything is stored in the same table. *father_id* and *mother_id* acts as references to the rows where father's and mother's information is stored. The combination of *father_id*, *mother_id* and *firstname* acts as a criterion, which uniquely identifies rows according to those three values (we suppose that parents give their children different names).

```sql
CREATE TABLE family_tree (
  -- define columns (name / type / default value / nullable)
  id             DECIMAL      NOT NULL,
  firstname      VARCHAR(50)  NOT NULL,
  lastname       VARCHAR(50)  NOT NULL,
  year_of_birth  DECIMAL      NOT NULL,
  year_of_death  DECIMAL,
  father_id      DECIMAL,
  mother_id      DECIMAL,
  -- the primary key
  CONSTRAINT family_tree_pk   PRIMARY KEY (id),
  -- an additional criterion to uniquely distinguish rows from each other
  CONSTRAINT family_tree_uniq UNIQUE (father_id, mother_id, firstname),
  -- two foreign keys (to the same table in this special case) to ensure that no broken links arise
  CONSTRAINT family_tree_fk1  FOREIGN KEY (father_id) REFERENCES family_tree(id),
  CONSTRAINT family_tree_fk2  FOREIGN KEY (mother_id) REFERENCES family_tree(id),
  -- plausibility checks
  CONSTRAINT family_tree_check1 CHECK ( year_of_birth >= 1800 AND year_of_birth < 2100),
  CONSTRAINT family_tree_check2 CHECK ((year_of_death >= 1800 AND year_of_death < 2100) OR year_of_death IS NULL)
);

-- a fictional couple
INSERT INTO family_tree VALUES ( 1, 'Karl',   'Miller', 1855, 1905, null, null);
INSERT INTO family_tree VALUES ( 2, 'Lisa',   'Miller', 1851, 1912, null, null);
-- their children
INSERT INTO family_tree VALUES ( 3, 'Ruth',   'Miller', 1878, 1888, 1,    2);
INSERT INTO family_tree VALUES ( 4, 'Helen',  'Miller', 1880, 1884, 1,    2);
INSERT INTO family_tree VALUES ( 5, 'Carl',   'Miller', 1882, 1935, 1,    2);
INSERT INTO family_tree VALUES ( 6, 'John',   'Miller', 1883, 1900, 1,    2);
-- some more people; some of them are descendants of the Millers
INSERT INTO family_tree VALUES ( 7, 'Emily',  'Newton', 1880, 1940, null, null);
INSERT INTO family_tree VALUES ( 8, 'Charly', 'Miller', 1908, 1978, 5,    7);
INSERT INTO family_tree VALUES ( 9, 'Deborah','Brown',  1910, 1980, null, null);
INSERT INTO family_tree VALUES (10, 'Chess',  'Miller', 1948, null, 8,    9);
COMMIT;
```

## Basic Queries

As a first example, we retrieve Mr. Karl Miller and all his descendants. To do so, we must retrieve his own row and define a rule, how to 'navigate' from level to level within the family tree.

```sql
-- Choose a name for the intermediate table and its columns. The column names may differ from the names in the real table.
WITH intermediate_table (id, firstname, lastname) AS
(
  -- Retrieve the starting row (or rows)
  SELECT id, firstname, lastname
  FROM   family_tree
  WHERE  firstname = 'Karl'
  AND    lastname  = 'Miller'
    UNION ALL
  -- Define the rule for querying the next level. In most cases this is done with a join operation.
  SELECT f.id, f.firstname, f.lastname        -- the alias 'f' refers to the real table
  FROM   intermediate_table i                 -- the alias 'i' refers to the intermediate table
  JOIN   family_tree f ON f.father_id = i.id OR f.mother_id = i.id  -- the join operation defines, how to reach the next level
)
-- The final SELECT
SELECT * FROM intermediate_table;
```

You can use all language features of SQL to process the intermediate table further. (It isn't a real table, it is only an intermediate result with the structure of a table).  For example, to count the number of descendants.

```sql
WITH ...  -- The 'with clause' as above
-- The final SELECT
SELECT count(*) FROM intermediate_table
;
```

To demonstrate the problems in situations where no recursive SELECT is available, we show a syntax with subqueries.

```sql
-- This query retrieves only Mr. Karl Miller ...
SELECT * 
FROM   family_tree
WHERE  firstname = 'Karl'
AND    lastname  = 'Miller'
  UNION ALL
-- ... and his children
SELECT * 
FROM   family_tree
WHERE  father_id IN (SELECT id
                     FROM   family_tree
                     WHERE  firstname = 'Karl'
                     AND    lastname  = 'Miller'
                    )
;
```

Every level has its own syntax, e.g., to retrieve grandchildren, we need a subquery within a subquery.

As a second example, we traverse the hierarchy in the opposite direction: from a person to their patrilineal (male-line) ancestors. In comparison to the first example, two things change. The start point of the query is no longer Mr. Karl Miller, as he has no ancestor in our example table. And we have to change the join condition by swapping id and father_id.

```sql
-- Retrieve ancestors
WITH intermediate_table (id, father_id, firstname, lastname) AS
(
  -- Retrieve the starting row (or rows)
  SELECT id, father_id, firstname, lastname  -- now we need the 'father_id'
  FROM   family_tree
  WHERE  firstname = 'Chess'
  AND    lastname  = 'Miller'
    UNION ALL
  -- Define the rule for querying the next level.
  SELECT f.id, f.father_id, f.firstname, f.lastname
  FROM   intermediate_table i
  JOIN   family_tree f ON f.id = i.father_id  -- compared with the first example this join operation defines the opposite direction
)
-- The final SELECT
SELECT * FROM intermediate_table
;
```

## Notice the Level

Sometimes we need to know to which level within the hierarchy or network a row belongs to. To display this level, we include a pseudo-column with an arbitrary name into the query. We choose the name *hier_level* (as *level* is a reserved word in the context of savepoints).

```sql
-- We extend the above example to show the hierarchy level
WITH intermediate_table (id, firstname, lastname, hier_level) AS
( SELECT id, firstname, lastname, 0 as hier_level         -- set the level of the start point to a fix number
  FROM   family_tree
  WHERE  firstname = 'Karl'
  AND    lastname  = 'Miller'
    UNION ALL
  SELECT f.id, f.firstname, f.lastname, i.hier_level + 1  -- increment the level
  FROM   intermediate_table i
  JOIN   family_tree f ON f.father_id = i.id OR f.mother_id = i.id
)
SELECT * FROM intermediate_table;
```

The level is now available, and we can use it as an additional condition, eg. for a restriction to the first two levels.

```sql
-- The with clause remains unchanged
...
SELECT * FROM intermediate_table WHERE hier_level < 2; -- restrict the result to the first two levels

-- or, as with the above solution the intermediate result set is computed over ALL levels and later restricted to the first two:
WITH intermediate_table (id, firstname, lastname, hier_level) AS
( SELECT id, firstname, lastname, 0 as hier_level
  FROM   family_tree
  WHERE  firstname = 'Karl'
  AND    lastname  = 'Miller'
    UNION ALL
  SELECT f.id, f.firstname, f.lastname, i.hier_level + 1
  FROM   intermediate_table i
  JOIN   family_tree f ON f.father_id = i.id OR f.mother_id = i.id
  WHERE  hier_level < 1   -- restrict the join to the expected result
)
SELECT * FROM intermediate_table;
```

## Create Paths

Sometimes we want to build a path from the starting point of the hierarchy or network to the actual row, eg. for a faceted classification like *1.5.3* or for a simple numbering of the visited nodes. This can be achieved in a similar way as the computing of the level. We need a pseudo-column with an arbitrary name and append actual values to those that have already been formed.

```sql
-- Save the path from person to person in an additional column. We choose the name 'hier_path' as its name. 
WITH intermediate_table (id, firstname, lastname, hier_level, hier_path) AS
( SELECT id, firstname, lastname, 0 as hier_level, firstname as hier_path -- we collect the given names
  FROM   family_tree
  WHERE  firstname = 'Karl'
  AND    lastname  = 'Miller'
    UNION ALL
  -- The SQL standard knows only a two-parameter function concat(). We us it twice.
  SELECT f.id, f.firstname, f.lastname, i.hier_level + 1, concat (concat (i.hier_path, ' / ' ), f.firstname)
  FROM   intermediate_table i
  JOIN   family_tree f ON f.father_id = i.id OR f.mother_id = i.id
)
SELECT * FROM intermediate_table;
```

## Depth First / Breadth First

There are two ways to traverse hierarchies and networks. You must decide which kind of nodes you want to process first: child nodes (nodes of the next level) or sibling nodes (nodes of the same level). The two methods are called *depth first* and *breadth first*. With the keywords `DEPTH FIRST` and `BREADTH FIRST` (the default) you can decide between the two variants.

```sql
<with_clause>
SEARCH [DEPTH FIRST|BREADTH FIRST] BY <column_name> SET <sequence_number>
<select_clause>
```

The key words occur between the `WITH clause` and the `SELECT clause`. Since - as opposed to a tree in a programming language like JAVA or C++ or like an XML instance - rows of a table have no implicit order, you must define an order for the nodes within their level. This is done behind the `BY` key word. After the `SET` key word, define the name of an additional pseudo-column, where a numbering over all rows is stored automatically.

```sql
WITH intermediate_table (id, firstname, lastname, hier_level) AS
( SELECT id, firstname, lastname, 0 AS hier_level
  FROM   family_tree
  WHERE  firstname = 'Karl'
  AND    lastname  = 'Miller'
    UNION ALL
  SELECT f.id, f.firstname, f.lastname, i.hier_level + 1
  FROM   intermediate_table i
  JOIN   family_tree f ON f.father_id = i.id OR f.mother_id = i.id
)
-- SEARCH BREADTH FIRST BY firstname SET sequence_number
SEARCH DEPTH FIRST BY firstname SET sequence_number
SELECT * FROM intermediate_table;
```

There are some notable remarks to the above query:
1. In contrast to the other queries on this page (where we implicitly have used the default `BREADTH FIRST`), the family tree is traversed in such a way that after every row its 'child' rows are processed. This is significant at level 1.
1. If there is more than one row per level, the rows are ordered according to the `BY` definition: *firstname* in this case.
1. The rows have a sequence number: *sequence_number* in this case. You may use this number for any additional processing.

## Exercises

**Exercise:** Retrieve Chess Miller and all Chess's **female** ancestors.

**Solution:**

```sql
WITH intermediate_table (id, mother_id, firstname, lastname) AS
(
  SELECT id, mother_id, firstname, lastname
  FROM   family_tree
  WHERE  firstname = 'Chess'
  AND    lastname  = 'Miller'
    UNION ALL
  SELECT f.id, f.mother_id, f.firstname, f.lastname
  FROM   intermediate_table i
  JOIN   family_tree f ON f.id = i.mother_id
)
SELECT * FROM intermediate_table;
```

**Exercise:** Retrieve Chess Miller and all Chess's ancestors: male and female.

**Solution:**

```sql
WITH intermediate_table (id, father_id, mother_id, firstname, lastname) AS
(
  SELECT id, father_id, mother_id, firstname, lastname
  FROM   family_tree
  WHERE  firstname = 'Chess'
  AND    lastname  = 'Miller'
    UNION ALL
  SELECT f.id, f.father_id, f.mother_id, f.firstname, f.lastname
  FROM   intermediate_table i
  -- extend the JOIN condition!
  JOIN   family_tree f ON (f.id = i.mother_id OR f.id = i.father_id)
)
SELECT * FROM intermediate_table;
```

**Exercise:** To make the situation a little bit more transparent add a number to the previous query which shows the actual level.

**Solution:**

```sql
WITH intermediate_table (id, father_id, mother_id, firstname, lastname, hier_level) AS
(
  SELECT id, father_id, mother_id, firstname, lastname, 0  -- we start with '0'
  FROM   family_tree
  WHERE  firstname = 'Chess'
  AND    lastname  = 'Miller'
    UNION ALL
  SELECT f.id, f.father_id, f.mother_id, f.firstname, f.lastname, i.hier_level + 1
  FROM   intermediate_table i
  JOIN   family_tree f ON (f.id = i.mother_id OR f.id = i.father_id)
)
SELECT * FROM intermediate_table;
```

**Exercise:** To make the situation absolutely transparent replace the level by some kind of path (child / parent / grandparent / ...).

**Solution:**

```sql
WITH intermediate_table (id, father_id, mother_id, firstname, lastname, ancestry) AS
(
  SELECT id, father_id, mother_id, firstname, lastname, firstname
  FROM   family_tree
  WHERE  firstname = 'Chess'
  AND    lastname  = 'Miller'
    UNION ALL
  SELECT f.id, f.father_id, f.mother_id, f.firstname, f.lastname, concat (concat (i.ancestry, ' / '), f.firstname)
  FROM   intermediate_table i
  JOIN   family_tree f ON (f.id = i.mother_id OR f.id = i.father_id)
)
SELECT * FROM intermediate_table;
```

**Exercise:** Retrieve all grandchildren of Karl Miller.

**Solution:**

```sql
WITH intermediate_table (id, father_id, mother_id, firstname, lastname, hier_level) AS
(
  SELECT id, father_id, mother_id, firstname, lastname, 0   -- we start with '0'
  FROM   family_tree
  WHERE  firstname = 'Karl'
  AND    lastname  = 'Miller'
    UNION ALL
  SELECT f.id, f.father_id, f.mother_id, f.firstname, f.lastname, i.hier_level + 1
  FROM   intermediate_table i
  JOIN   family_tree f ON (f.father_id = i.id AND hier_level < 2) -- performance: abort joining after the second level
)
SELECT * FROM intermediate_table WHERE hier_level = 2; -- this is the restriction to the grandchildren
```

**Exercise:** Retrieve every person in the table *family_tree* and show its firstname and the firstname of its very first known ancestor in the male line.

**Solution:**

```sql
WITH intermediate_table (id, father_id, firstname, lastname, initial_row, hier_level) AS
( -- The starting points are persons (more than one in our example table) for which no father is known.
  SELECT id, father_id, firstname, lastname, firstname, 0
  FROM   family_tree
  WHERE  father_id IS NULL
    UNION ALL
  -- The start name is preserved from level to level
  SELECT f.id, f.father_id, f.firstname, f.lastname, i.initial_row, i.hier_level + 1
  FROM   intermediate_table i
  JOIN   family_tree f ON f.father_id = i.id
)
SELECT * FROM intermediate_table;
-- or:
... unchanged 'with clause'
SELECT id, firstname, '-->', initial_row, 'in ', hier_level, 'generation(s)' FROM intermediate_table;
```

**Exercise:** a) How many descendants of Carl Miller are stored in the example table?
b) Same question as before, but differentiated per level.

**Solution:**

```sql
-- a)
WITH intermediate_table (id, firstname, lastname, hier_level) AS
( SELECT id, firstname, lastname, 0 AS hier_level
  FROM   family_tree
  WHERE  firstname = 'Karl'
  AND    lastname  = 'Miller'
    UNION ALL
  SELECT f.id, f.firstname, f.lastname, i.hier_level + 1
  FROM   intermediate_table i
  JOIN   family_tree f ON f.father_id = i.id
)
SELECT count(*) FROM intermediate_table where hier_level > 0;
-- b) Use the same WITH clause. Only the final SELECT changes.
...
SELECT hier_level, count(hier_level) FROM intermediate_table WHERE hier_level > 0 GROUP BY hier_level;
```
