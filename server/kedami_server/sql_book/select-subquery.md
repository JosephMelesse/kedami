# SELECT: Subquery

A subquery is a complete SELECT command which is used within another SELECT, UPDATE, INSERT or DELETE command. The only difference to a simple SELECT is, that it is enclosed in parenthesis.

## Classification

Depending on the type of the created result there are three classes of subqueries:
* *Scalar Value Subquery*: The subquery returns one single value, e.g: `(SELECT max(weight) FROM person)`.
* *Row Subquery*: The subquery returns one single row of one or more values, e.g: `(SELECT min(weight), max(weight) FROM person)`.
* *Table Subquery*: The subquery returns a list of rows, which is a table, e.g: `(SELECT lastname, weight FROM person)`. For the classification, it makes no difference whether the resulting list contains zero, one, or more rows. The demarcation between a table subquery and a row subquery is that **potentially** more than one row may occur.

Every type can be used on all positions where the type it stands for may occur: the scalar value subquery where a single value may occur, the row subquery where a single row may occur and the table subquery where a table may occur. Additionally, table subqueries may occur as an argument of an EXISTS, IN, SOME, ANY or ALL predicate.

Independent from this classification subqueries may be *correlated subqueries* or *non-correlated subqueries*. Correlated subqueries have a correlation to the surrounding query by the fact that they use values from the surrounding query within the subquery. Non-correlated subqueries are independent of the surrounding query. This distinction is shown in detail in the next chapter but applies also to the other two subquery classes.

Because correlated subqueries use values, which are determined by the surrounding query and may change from row to row, the subquery is executed - conceptually - as often as resulting rows of the surrounding query exist. This might lead to performance problems. Nevertheless correlated subqueries are an often used construct. In many cases, there are equivalent constructs which use a JOIN. Which one shows the better performance depends highly on the DBMS, and the number of involved rows, the existence of indices, and a lot more variables.

## Scalar Value Subquery

The first example creates a list of lastnames, weights and the average weight of all persons.

```sql
SELECT id,
       lastname,
       weight,
       (SELECT avg(weight) FROM person) AS 'avg_weight'  -- this is the subquery
FROM   person
ORDER BY lastname;
```

Because the subquery uses the `avg()` function, the SQL compiler knows that it will return exactly one single value. Therefore it's type is *Scalar Value Subquery* and can be used on positions where scalar values may occur, e.g. in the list between SELECT and FROM.

In the next example, the subquery is used as a deputy for a value within the WHERE clause.

```sql
-- Persons who weigh more than the average of all persons
SELECT id, lastname, weight
FROM   person
WHERE  weight >= (SELECT avg(weight) FROM person)   -- another position for the subquery
ORDER BY lastname;
```

Both examples use the table *person* twice. One can also use different tables. There is no dependency between the table name in the subquery and in the surrounding query. This applies to all classes of correlated and non-correlated subqueries. The subqueries may retrieve any value from any other table, e.g. the number of contacts.

These first two examples show non-correlated subqueries, which means, that the subqueries are independent from the queries in which they are embedded. They are executed only once.

But often an application faces a situation, where the subquery must use values from the outside query (similar to subroutines which uses parameters). This kind of subquery is called a correlated subquery. As an example, the next query lists persons together with the average weight of their family.

```sql
SELECT id, firstname, lastname, weight,
       (SELECT avg(weight)
        FROM   person sq                -- 'sq' is an arbitrary alias name for the table in the subquery
        WHERE  sq.lastname = p.lastname -- identify the inner and outer table by its alias names
       ) family_average                 -- an arbitrary alias name for the computed family average
FROM   person p                         -- 'p' is an arbitrary alias name for the table in the surrounding query
ORDER BY lastname, weight;
```

The subselect gets one row of the surrounding SELECT after the next as an parameter with the name 'p'. Within the subselect all columns of the row 'p' are known and may be used. Here the family name from the outside row is used in the subquery to find all persons within the family and the average weight of the family members.

Be careful: Correlated subqueries are executed once per row of the surrounding query. Therefore they are much more costly than non-correlated subqueries. There might exist an equivalent solution using JOIN or GROUP BY which works with better performance. The query optimizer of the DBMS internally might rearrange the given subquery into one of the equivalent forms. But this does not work in all cases.

The distinction between correlated and non-correlated subqueries is universal. It applies also to the other subquery classes.

## Row Subquery

This example retrieves one or more persons, whose firstname is the lowest (in the sense of the lexical order) of all firstnames and whose lastname is the lowest of all lastnames. Because of the AND condition it might be the case that no person is found.

```sql
-- One resulting row: Elias Baker
SELECT *
FROM   person
WHERE  (firstname, lastname) = (SELECT MIN(firstname), MIN(lastname) FROM person);
```

Within the subquery, the lowest first- and lastnames are retrieved. The use of the `min()` function guarantees that not more than one row with two columns will arise - therefore it is a row subquery. In the surrounding query, this intermediate result is compared with each row of the complete table *person* or - if present - an index is used.

It is fortunate that the command retrieves a row. In most cases, the lowest first- and lastname results from different persons. But also in those cases, the command is syntactically correct and will not throw any exception.

In the next example, persons with the lowest first- and lastnames within every family are retrieved. To do so, it is necessary to use a correlated row subquery.

```sql
-- 7 rows, one per family
SELECT *
FROM   person p
WHERE (firstname, lastname) =
  (SELECT MIN(firstname), MIN(lastname) FROM person sq where p.lastname = sq.lastname);
```

Again, there are the two incarnations of table *person*, one with the alias name 'p' in the surrounding query and one with the alias name 'sq' in the subquery. The subquery is called once per resulting row of the surrounding query, because the 'p.lastname' may change with every row of 'p'.

Within every family there is at least one person which achieves the condition - it is also conceivable that several persons achieve the condition.

## Table Subquery

The next example retrieves persons who have a contact. The class of the subquery is: non-correlated table subquery (used as a condition in the IN predicate).

```sql
SELECT * 
FROM   person 
WHERE  id IN 
  (SELECT person_id FROM contact);  -- the subquery
```

The subquery creates multiple rows with one column for each of them. This constitutes a new, intermediate table. Therefore this example is a table subquery.

The IN operator is able to act on this intermediate table. In contrast, it is not possible to use operators like '=' or '>' on this kind of intermediate result. In this case, the SQL compiler will recognize a syntax error.

The next example is an extension of the first one. It adds a correlation criterion between the query and the subquery by requesting the lastname within an email-address.

```sql
-- A correlated table subquery, looking for lastnames within e-mail-addresses
SELECT * 
FROM   person p
WHERE  id IN 
  (SELECT person_id 
   FROM   contact c
   WHERE  c.contact_type = 'email'
   AND    UPPER(c.contact_value) LIKE CONCAT(CONCAT('%', UPPER(p.lastname)), '%'));
```

The last comparison after the AND is a little bit complex. It uses the functions CONCAT() and UPPER() as well as the predicate LIKE, but this is not of interest for the actual topic 'subquery'. The important part is that the subquery refers to 'p.lastname' of the surrounding query. Only Mr. Goldstein meets the criterion that his e-mail address contains his lastname when the two columns are compared case-insensitive.

Remark: CONCAT() concatenates two strings. UPPER() converts a string to the upper-case. LIKE in combination with the '%' sign looks for one string within another.

Next, there is an example where a non-correlated table subquery is object to a join operation.

```sql
-- Persons plus maximum weight of their family
SELECT *
FROM   person p
JOIN   (SELECT lastname, max(weight) max_fam_weight
        FROM   person
        GROUP BY lastname
       ) AS sq ON p.lastname = sq.lastname   -- join criterion between subquery table 'sq' and table 'p'
;
```

## Another Example

The example shows a solution to a common problem. Sometimes there are rows describing an outdated stage of entities. Those rows - for one logical entity - differ from each other in some columns and there is an additional column *version* to track the time flow.

Here is the example table *booking* and its data.

```sql
-- The table holds actual and historical values
CREATE TABLE booking (
  -- identifying columns
  id             DECIMAL      NOT NULL,
  booking_number DECIMAL      NOT NULL,
  version        DECIMAL      NOT NULL,
  -- describing columns
  state          CHAR(10)     NOT NULL,
  enter_ts       TIMESTAMP    NOT NULL,
  enter_by       CHAR(20)     NOT NULL,
  -- ...
  -- select one of the defined columns as the Primary Key
  CONSTRAINT booking_pk PRIMARY KEY (id),
  -- forbid duplicate recordings
  CONSTRAINT booking_unique UNIQUE (booking_number, version)
);

-- Add data
INSERT INTO booking VALUES (1, 4711, 1, 'created',   TIMESTAMP'2014-02-02 10:01:01', 'Emily');
INSERT INTO booking VALUES (2, 4711, 2, 'modified',  TIMESTAMP'2014-02-03 11:10:01', 'Emily');
INSERT INTO booking VALUES (3, 4711, 3, 'canceled',  TIMESTAMP'2014-02-10 09:01:01', 'John');
--
INSERT INTO booking VALUES (4, 4712, 1, 'created',   TIMESTAMP'2014-03-10 12:12:12', 'Emily');
INSERT INTO booking VALUES (5, 4712, 2, 'delivered', TIMESTAMP'2014-03-12 06:01:00', 'Charles');
--
INSERT INTO booking VALUES (6, 4713, 1, 'created',   TIMESTAMP'2014-03-11 08:50:02', 'Emily');
INSERT INTO booking VALUES (7, 4713, 2, 'canceled',  TIMESTAMP'2014-03-12 08:40:12', 'Emily');
INSERT INTO booking VALUES (8, 4713, 3, 'reopend',   TIMESTAMP'2014-03-13 10:04:32', 'Jack');
INSERT INTO booking VALUES (9, 4713, 4, 'delivered', TIMESTAMP'2014-03-15 06:40:12', 'Jack');
--
COMMIT;
```

The problem is to retrieve all **actual** rows, which are those with the highest version number within each booking. Bookings are considered to be the same if they have the same booking_number.

The first solution uses a non-correlated table subquery.

```sql
SELECT *
FROM   booking b
WHERE  (booking_number, version) IN
  (SELECT booking_number, MAX(version) FROM booking sq GROUP BY booking_number) -- the subquery
ORDER BY booking_number;
```

The subquery creates a list of booking numbers together with their highest version. This list is used by the surrounding query to retrieve the required rows with all its columns.

The second solution uses a correlated scalar value subquery.

```sql
SELECT *
FROM   booking b
WHERE  version =
  (SELECT max(version) FROM booking sq WHERE sq.booking_number = b.booking_number)
ORDER BY booking_number;
```

The surrounding query retrieves all rows of the table. For each of them, it calls the subquery, which retrieves the highest version within this booking_number. In most cases, this highest version differs from the version of the actual row and because of the '=' operator those rows are not part of the result. Only those, whose version is equal to the value determined in the subquery (and whose booking_number is the same as those used in the subquery) are part of the final result.

A variation of the introducing question may be to retrieve only historical rows (all versions except the highest one) for one special booking.

```sql
SELECT *
FROM   booking b
WHERE  version !=
  (SELECT max(version) FROM booking sq WHERE sq.booking_number = b.booking_number)
AND    booking_number = 4711
ORDER BY version;
```

The surrounding query restricts the rows to those of one special booking. The subquery is called only for those rows.

It's easy to run into pitfalls:

```sql
-- Unexpected result!
SELECT *
FROM   booking b
WHERE  version != (SELECT max(version) FROM booking)
AND    booking_number = 4711
ORDER BY version;
```

The above query returns all versions of booking 4711 including the actual one! To get the expected result, it's necessary to 'link' the surrounding query and the subquery together.

## Exercises

**Exercise:** Find the booking with the most versions.

**Solution:**

```sql
-- The subselect return exactly ONE single value. Therefor it's a (non-correlated) single value subquery.
-- But this is only a intermediate result. The final result may contain several rows, which is not the case in our example database!
SELECT *
FROM   booking
WHERE  version = (SELECT MAX(version) FROM booking);
```

**Exercise:** Find all bookings with are canceled (in the latest version).

**Solution:**

```sql
-- It's necessary to link the subquery with the surrounding query.
SELECT *
FROM   booking b
WHERE  version =
  (SELECT MAX(version) FROM booking sq WHERE sq.booking_number = b.booking_number)
AND    state = 'canceled';

-- Additionally within the resulting rows there must be a correlation between the version and the state.
-- This is accomplished with the AND keyword at the level of the surrounding query. If the AND works within
-- the subquery, the result does not meet the expectations.
SELECT *
FROM   booking b
WHERE  version =
  (SELECT MAX(version) FROM booking sq WHERE sq.booking_number = b.booking_number AND state = 'canceled');
```

**Exercise:** Create a list of all persons. For each person include the number of persons born in the same city as the person.

**Solution:**

```sql
-- The subselect uses the place_of_birth of the outside row. Therefore it's a correlated subquery.
SELECT firstname,
       lastname,
       place_of_birth,
       (SELECT COUNT(*) FROM person sq WHERE p.place_of_birth = sq.place_of_birth) cnt -- an arbitrary name for the additional column
FROM   person p;
```

**Exercise:** Create a list of all persons together with the number of their contact information.

**Solution:**

```sql
-- The subselect uses the ID of the outside row. Therefore it's a correlated subquery.
SELECT firstname,
       lastname,
       (SELECT COUNT(*) FROM contact c WHERE p.id = c.person_id) cnt -- an arbitrary name for the additional column
FROM   person p;
```

**Exercise:** Create a list of all persons together with the number of their e-mail-addresses.

**Solution:**

```sql
SELECT firstname,
       lastname,
       (SELECT COUNT(*)
        FROM   contact c
        WHERE  p.id = c.person_id
        AND    contact_type = 'email'  -- The subselect is a complete SELECT. Therefor all elements of
                                       -- a 'regular' SELECT may be used: Join, functions, ... and: SUBSELECT
       ) cnt                           -- an arbitrary name of the additional column
FROM   person p;
```

**Exercise:** Create a list of all persons together with the number of their contact information. (Same question as above.)
 Replace the subquery by a JOIN construct.

**Solution:**

```sql
-- Step 1 (for demonstration purpose only): To retrieve ALL persons, it's necessary to use an OUTER JOIN
SELECT firstname,
       lastname,
       c.contact_type
FROM   person p
LEFT OUTER JOIN contact c ON p.id = c.person_id;
-- 
-- Step 2 (complete solution): Add the counter. To do so, the result must be grouped.
SELECT firstname,
       lastname,
       count(c.contact_type)
FROM   person p
LEFT OUTER JOIN contact c ON p.id = c.person_id
GROUP BY firstname, lastname;
```

**Exercise:** For which persons there are NO contact information?

**Solution:**

```sql
-- The subquery returns more than one row. Therefore it's a table subquery.
SELECT firstname, lastname
FROM   person
WHERE  id NOT IN (SELECT person_id FROM contact);  -- the subquery
```
