# NULLs and the Three Valued Logic

## The Problem

As mentioned in a previous chapter of this wikibook and in wikipedia sometimes there is no value in a column of a row, or - to say it the other way round - the column stores the *NULL marker* (a flag to indicate the absence of any data), or - to use the notion of the SQL standard - the column stores the *NULL value*. This NULL marker is very different from the numeric value zero or a string with a length of zero characters! Typically it occurs when an application yet hasn't stored anything in the column of this row.

(A hint to Oracle users: For Oracle, the NULL marker is identical to a string of zero characters.)

The existence of the NULL marker introduces a **new fundamental problem**. In the usual boolean logic, there are the two logical values TRUE and FALSE. Every comparison evaluates to one of the two - and the comparisons negation evaluates to the opposite one. If a comparison evaluates to TRUE, its negation evaluates to FALSE and vice versa. As an example, in the usual boolean logic, one of the following two comparisons is TRUE, and the other one is FALSE: 'x < 5', 'x >= 5'.

Imagine now the new situation that x holds the NULL marker. It is not feasible that 'NULL < 5' is true (1). But can we say 'NULL < 5' is false (2) and its negation 'NULL >= 5' is true (3)? Is (3) more feasible than (1)? Of course not. (1) and (3) have the same 'degree of truth', so they shall evaluate to the same value. And this value must be different from TRUE and FALSE.

Therefore the usual boolean logic is extended by a third logic value. It is named **UNKNOWN**. All comparisons to the NULL marker results per definition in this new value. And the well-known statement 'if a statement is true, its negation is false' gets lost because there is a third option.

SQL's logic is an implementation of this so-called trivalent, ternary or three-valued logic (3VL). The existence of the NULL marker in SQL is not without controversy. But if NULLs are accepted, the 3VL is a necessity.

This page proceeds in two stages: First, it explains the handling of NULLs concerning comparisons, grouping, etc. . Second, it explains the boolean logic for the cases where the new value UNKNOWN interacts with any other boolean value - including itself.

## Example Table

To demonstrate NULL behaviors, we define an example tables: t1, and t2.

```sql
CREATE TABLE t1 (
  id    DECIMAL PRIMARY KEY,
  col_1 DECIMAL,
  col_2 VARCHAR(20),
  col_3 DECIMAL
);

INSERT INTO t1 VALUES ( 1,  1,    'Hello World', 1);
INSERT INTO t1 VALUES ( 2,  2,    NULL,          2);
INSERT INTO t1 VALUES ( 3,  3,    'Hello World', NULL);
INSERT INTO t1 VALUES ( 4,  4,    'Hello World', NULL);
INSERT INTO t1 VALUES ( 5,  5,    'Hello Their', NULL);
INSERT INTO t1 VALUES ( 6,  NULL, 'Hello World', NULL);
INSERT INTO t1 VALUES ( 7,  NULL, 'Hello World', NULL);
INSERT INTO t1 VALUES ( 8,  8,    'Hello World', NULL);
INSERT INTO t1 VALUES ( 18, 18,   'Hello World', NULL);

CREATE TABLE t2 (
  id DECIMAL PRIMARY KEY,
  col_x DECIMAL
);

INSERT INTO t2 VALUES ( 1, 1 );
INSERT INTO t2 VALUES ( 2, NULL );
INSERT INTO t2 VALUES ( 3, 3 );
INSERT INTO t2 VALUES ( 4, 4 );
INSERT INTO t2 VALUES ( 5, 5 );
INSERT INTO t2 VALUES ( 18, 18 );
COMMIT;
```

## Step 1: Evaluation of NULLs

### Comparison Predicates, IS NULL Predicate

SQL knows the six comparison predicates <, <=, =, >=, > and <> (unequal). Their main purpose is the arithmetic comparison of numeric values. Each of them needs two variables or constants (infix notation). This implies that it is possible that one or even both operands hold the NULL marker. As stated before, the common and very simple rule is: "All comparisons to the NULL marker results per definition in this new value (**unknown**).". Here are some examples:
* NULL = 5  evaluates to UNKNOWN.
* 5 = NULL  evaluates to UNKNOWN.
* NULL <= 5  evaluates to UNKNOWN.
* col_1 = 5  evaluates to UNKNOWN for rows where col_1 holds the NULL marker.
* col_1 = col_2  evaluates to UNKNOWN for rows where col_1 or col_2 holds the NULL marker.
* NULL = NULL  evaluates to UNKNOWN.
* col_1 = col_2  evaluates to UNKNOWN for rows where col_1 and col_2 holds the NULL marker.
The WHERE clause returns such rows where it evaluates to TRUE. It does not return rows where it evaluates to FALSE or to UNKNOWN. In consequence, it is not guaranteed that the following SELECT will return the complete table *t1*:

```sql
-- This SELECT will not return such rows where col_1 holds the NULL marker.
SELECT *
FROM   t1
WHERE  col_1 > 5
OR     col_1 = 5
OR     col_1 < 5;
```

Of course, there are use cases where rows with the NULL marker must be retrieved. Because the arithmetic comparisons are not able to do so, another language construct must do the job. It is the *IS NULL predicate*.

```sql
-- This SELECT will return exactly these rows where col_1 holds the NULL marker.
SELECT *
FROM   t1
WHERE  col_1 IS NULL;
```

### Other Predicates

For the other predicates, there is no simple rule of thumb. They must be explained one after the other.

The IN predicate is a shortcut for a sequence of OR operations:

Only the two comparisons 'col_1 = 3' and 'col_1 = 18' are able to retrieve rows (possibly many rows). The comparison 'col_1 = NULL' will never evaluate to TRUE. It's always UNKNOWN, even if col_1 holds the NULL marker. To retrieve those rows, it's necessary - as shown above - to use the 'IS NULL' predicate.

```sql
-- Shortcut for: col_1 = 3 OR col_1 = 18 OR col_1 = NULL
SELECT *
FROM   t1
WHERE  col_1 IN (3, 18, NULL);  -- the NULL case will never hit with the IN predicate!
```

This is a little more complex. This will only return 1, 3, and 4, the items that don't have NULL in t2.col_x or t1.col_1.

```sql
SELECT *
FROM   t1
WHERE  col_1 IN (SELECT col_x FROM t2 WHERE id < 10);
```

The subselect of an EXISTS predicate evaluates to TRUE if the cardinality of the retrieved rows is greater than 0, and to FALSE if the cardinality is 0. It is not possible that the UNKNOWN value occurs.

```sql
-- The subselect to t2 can hit some rows - or not. If there are hits in the subselect, ALL rows of t1
-- are returned, else no rows of t1 are returned.
SELECT *                                 -- The select to table t1
FROM   t1
WHERE  EXISTS
       (SELECT * FROM t2 WHERE id < 10); -- The subselect to table t2
```

The LIKE predicate compares a column with a regular expression. If the column contains the NULL marker, the LIKE predicate returns the UNKNOWN value, which means that the row is not retrieved.

```sql
-- The LIKE retrieves only rows where col_2 matches the WHERE statement and col_2 is not NULL.
SELECT *
FROM   t1
WHERE  col_2 LIKE 'Hello %';
```

### Predefined Functions

The aggregate functions `COUNT(<column_name>), MIN(<column_name>), MAX(<column_name>), SUM(<column_name>)` and `AVG(<column_name>)` ignores such rows where <column_name> contains the NULL marker. On the other hand `COUNT(*)` includes all rows.

If a parameter of one of the scalar functions like `UPPER(), TRIM(), CONCAT(), ABS(), SQRT(), ...` contains the NULL marker the resulting value is - in the most cases - the NULL marker.

### Grouping

There are some situations where column values are compared to each other to answer the question, whether they are distinct. For usual numbers and strings, the result of such decisions is obvious. But how shall the DBMS handle NULL markers? Are they distinct from each other, are they equal to each other or is there no answer to this question at all? To get results, which are expected by (nearly) every end-user, the standard defines "Two null values are not distinct.", they build a single group.

`SELECT DISTINCT col_1 FROM t1;` retrieves one and only row for all rows where *col_1* holds the NULL marker.

`... GROUP BY col_1 ...;` builds one and only one group for all rows where *col_1* holds the NULL marker.

## Step 2: Boolean Operations within three-valued logic (3VL)

After we have seen how various comparisons and predicates on the NULL marker produce TRUE, FALSE, and UNKNOWN, it's necessary to explain the rules for the new logic value UNKNOWN.

### Inspection

A first elementary operation is the inspection of a truth value: is it TRUE, FALSE or UNKNOWN? Analogous to the *IS NULL predicate* there are three additional predicates:
* IS [NOT] TRUE
* IS [NOT] FALSE
* IS [NOT] UNKNOWN

```sql
-- Check for 'UNKNOWN'
SELECT *
FROM   t1
WHERE  (col_1 = col_3) IS UNKNOWN;  -- parenthesis are not necessary

-- ... is semantically equivalent to
SELECT *
FROM   t1
WHERE  col_1 IS NULL 
OR     col_3 IS NULL;
```

In the abstract syntax of logical systems *p* shall represent any of its truth values. Here is the three-valued logic truth table:

| *p* | IS TRUE | IS FALSE | IS UNKNOWN |   | IS NOT TRUE | IS NOT FALSE | IS NOT UNKNOWN |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TRUE | TRUE | FALSE | FALSE |   | FALSE | TRUE | TRUE |
| FALSE | FALSE | TRUE | FALSE |   | TRUE | FALSE | TRUE |
| UNKNOWN | FALSE | FALSE | TRUE |   | TRUE | TRUE | FALSE |

All predicates lead to TRUE or FALSE and never to UNKNOWN.

### NOT

The next operation is the negation of the new value. Which values evaluate to 'NOT UNKNOWN'? The UNKNOWN value represents the impossibility to decide between TRUE and FALSE. It is not feasible that the negation of this impossibility leads to TRUE or FALSE. Likewise, it is UNKNOWN.

```sql
-- Which rows will match?  (1)
SELECT *
FROM   t1
WHERE  NOT col_2 = NULL; -- 'col_2 = NULL' evaluates to UNKNOWN in all cases, see above.

-- Is this SELECT equivalent to the first one?  (2)
SELECT *
FROM   t1
  EXCEPT
SELECT *
FROM   t1
WHERE  col_2 = NULL;

-- No, it's different!! Independent from NULL markers in col_2, (1) retrieves
-- absolutely NO row and (2) retrieves ALL rows.
```

The above SELECT (1) will retrieve no rows as 'NOT col_2 = NULL' evaluates to the same as 'col_2 = NULL', namely UNKNOWN. And the SELECT (2) will retrieve all rows, as the part after EXCEPT will retrieve no rows, hence only the part before EXCEPT is relevant.

In the abstract syntax of logical systems *p* shall represent any of its truth values and NOT *p* its negation. Herein the following table applies:

| *p* | NOT *p* |
| --- | --- |
| TRUE | FALSE |
| FALSE | TRUE |
| UNKNOWN | UNKNOWN |

### AND, OR

There are the two binary operations AND and OR. They evaluate as follows:

| *p* | *q* | *p* AND *q* | *p* OR *q* |
| --- | --- | --- | --- |
| TRUE | TRUE | TRUE | TRUE |
| TRUE | FALSE | FALSE | TRUE |
| TRUE | UNKNOWN | UNKNOWN | TRUE |
| FALSE | TRUE | FALSE | TRUE |
| FALSE | FALSE | FALSE | FALSE |
| FALSE | UNKNOWN | FALSE | UNKNOWN |
| UNKNOWN | TRUE | UNKNOWN | TRUE |
| UNKNOWN | FALSE | FALSE | UNKNOWN |
| UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

The precedence of the operations is defined as usual: IS predicate, NOT, AND, OR.

## Some Examples

```sql
--
-- Add a new row to the test data base
INSERT INTO person (id, firstname, lastname)  -- Omit some columns to generate NULL markers
VALUES             (99, 'Tommy',   'Test');
COMMIT;

SELECT *
FROM   person
-- focus all tests to the new row
WHERE  id = 99                  -- (1): TRUE 
AND                             -- (3): (1) AND (2) ==> TRUE AND UNKNOWN ==> UNKNOWN
(
       date_of_birth = NULL     -- (2): UNKNOWN
);                              -- no hit

SELECT *
FROM   person
WHERE  id = 99                  -- (1): TRUE 
AND                             -- (3): (1) AND (2) ==> TRUE AND TRUE ==> TRUE
(
       date_of_birth IS NULL    -- (2): TRUE
);                              -- hit

SELECT *
FROM   person
WHERE  id = 99                  -- (1): TRUE 
OR                              -- (3): (1) OR (2) ==> TRUE OR UNKNOWN ==> TRUE
(
       date_of_birth = NULL     -- (2): UNKNOWN
);                              -- hit

SELECT *
FROM   person
WHERE  id = 99                  -- (1): TRUE 
AND                             -- (4): (1) AND (3) ==> TRUE AND FALSE ==> FALSE
(
NOT                             -- (3): NOT (2) ==> NOT TRUE ==> FALSE
       date_of_birth IS NULL    -- (2): TRUE

);                              -- no hit (same as AND date_of_birth IS NOT NULL)

-- Clean up the test database
DELETE FROM person WHERE id = 99;
DROP TABLE IF EXISTS t1, t2;     
COMMIT;
```
