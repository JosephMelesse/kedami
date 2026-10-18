# Retrieve Top N Rows per Group

"Technology evolves from the primitive over the complex to the simple." (Antoine de Saint-Exupery)

## The Challenge

Often there is the requirement to access the first or top n rows for every unique value of a given column: the cheapest product (= first row) within a product group (= unique values of the given column), the rows with the highest version number per entity within a historic table, the newest 10 log entries per user, ... . In the SQL world, this is a three-step-job: a) group the table over the given column b) order the rows within the created groups according to a criteria and c) access the first or the top n rows within the created, ordered groups.

In complex cases like this one SQL does not offer only a single solution. There are multiple formulations to get the expected result. At the logical level, they are equivalent, but it is likely that their performance differs strongly from each other. And it's likely that the performance of the same formulation differs strongly on different database systems. The deviation in performance results from the fact that SQL in general defines only WHAT the system shall do and not HOW it shall be done. It is the responsibility of the database system to find an optimal execution plan.

We offer some of the possible solutions - from primitive over complex to simple ones. They include subselects, joins, the `FETCH FIRST` clause, the use of a predicate, and finally `window functions` as the method of choice.

## Example Table and Data

We use the example table `product` with a small number of data rows to discuss diverse strategies.

```sql
CREATE TABLE product (
  id             INTEGER      NOT NULL,
  name           VARCHAR(50)  NOT NULL,
  product_group  VARCHAR(20)  NOT NULL,
  prize          DECIMAL(5,2)         ,
  CONSTRAINT product_pk PRIMARY KEY (id)
);

INSERT INTO product VALUES ( 1, 'Big Fat One'    , 'Desktop',    545);
INSERT INTO product VALUES ( 2, 'SmartAndElegant', 'Laptop',     675);
INSERT INTO product VALUES ( 3, 'Angle',           'Laptop',     398);
INSERT INTO product VALUES ( 4, 'Wizzard 7',       'Smartphone', 380);
INSERT INTO product VALUES ( 5, 'Solid',           'Desktop',    565);
INSERT INTO product VALUES ( 6, 'AllRounder',      'Smartphone', 535);
INSERT INTO product VALUES ( 7, 'WhiteHorse',      'Laptop',     675);
INSERT INTO product VALUES ( 8, 'Workstation ONE', 'Desktop',    499);
INSERT INTO product VALUES ( 9, 'Air',             'Laptop',     450);
INSERT INTO product VALUES (10, 'Rusty',           'Laptop',     390);
INSERT INTO product VALUES (11, 'Tripple-A',       'Desktop',    580);
INSERT INTO product VALUES (12, 'Oxygen 8',        'Smartphone', 450);
INSERT INTO product VALUES (13, 'AllDay Basic',    'Smartphone',  75);
COMMIT;
```

With this structure and data, we will try to access the rows with the highest prize per product group.

## Insufficient Solutions

### Example 1

The first solution uses only the `GROUP BY` clause and reduces the problem in two ways: a) it offers only the very first row per group (ignoring the second best, third best, etc. rows) by using the functions max() or min() and b) the solution has only access to the grouping criteria and the result of max() / min(). However, due to the nature of the `GROUP BY` clause all remaining columns are not accessible - see here.

```sql
SELECT product_group, MAX(prize)
FROM   product
GROUP BY product_group;


product_group | max
--------------+-----
Smartphone    | 535
Desktop       | 580
Laptop        | 675

-- access to other columns is not possible
SELECT *
FROM   product
GROUP BY product_group;
```

### Example 2

We can extend this first solution to show more columns by combining it with a correlated or non-correlated subquery. This second solution offers access to all columns. Nevertheless, the result is not what we expect as the number of accessed rows is 4. The `MAX(prize)` criteria is not necessarily unique. Thus we receive 4 rows for the 3 groups out of our small example table. And - as mentioned above - we don't have access to the row with the second-highest prize.

```sql
-- SELECT with a non-correlated subquery. The subquery is executed only once.
SELECT *
FROM   product
WHERE  prize IN      -- prize is a very weak criterion
  (SELECT MAX(prize)
   FROM   product
   GROUP BY product_group
  )
;

id |      name       | product_group | prize
---+-----------------+---------------+-------
11 | Tripple-A       | Desktop       |   580
 2 | SmartAndElegant | Laptop        |   675
 7 | WhiteHorse      | Laptop        |   675
 6 | AllRound        | Smartphone    |   535


-- SELECT with a correlated subquery. Observe the performance! The subquery is executed
-- once per row of p1 !!!
SELECT *
FROM   product p1
WHERE  prize IN      -- prize is a very weak criterion
  (SELECT MAX(prize)
   FROM   product p2
   WHERE  p1.product_group = p2.product_group
  )
;

id |      name       | product_group | prize
---+-----------------+---------------+-------
11 | Tripple-A       | Desktop       |   580
 2 | SmartAndElegant | Laptop        |   675
 7 | WhiteHorse      | Laptop        |   675
 6 | AllRound        | Smartphone    |   535
```

There are problems with these methods. If one uses nothing but the `GROUP BY` clause, the complete set columns and rows won't be displayed. If the `GROUP BY` is put into a subquery, all columns are displayed, but multiple rows for the same column will be displayed if more than one row meets the criteria.

### Example 3

The same holds true for the third solution. One can create a `JOIN` over the product_group and reduce the resulting rows to those with the highest prize within the group by using the `HAVING` clause. The result is the same as with the second solution.

```sql
SELECT p1.*
FROM   product p1
JOIN   product p2 ON (p1.product_group = p2.product_group)
GROUP BY p1.id, p1.name, p1.product_group, p1.prize
HAVING p1.prize = MAX(p2.prize)
;

id |      name       | product_group | prize
---+-----------------+---------------+-------
 7 | WhiteHorse      | Laptop        |   675
 2 | SmartAndElegant | Laptop        |   675
11 | Tripple-A       | Desktop       |   580
 6 | AllRound        | Smartphone    |   535
```

### Example 4

As the fourth solution we offer a last example how to express the same issue - with the same imperfect result. It uses a `NOT EXISTS` predicate to search those rows, to which there is no higher prize within their group.

```sql
SELECT *
FROM   product p1
WHERE NOT EXISTS
  (SELECT *
   FROM  product p2
   WHERE p1.product_group = p2.product_group
   AND   p1.prize < p2.prize
  )
;
```

## Complex Solutions

To overcome the above shortcomings we make 2 adjustments. First, the link between the two `SELECT`s (via join or subselect) must be changed to a column, with unique values. We will use the ID column. Second, we must use the `FETCH  FIRST` clause in combination with an `ORDER BY` to count rows.

### Example 5

First, we show a modification of the upper second solution. The `ORDER BY` clause sorts the rows into the desired sequence.  The `FETCH FIRST` clause restricts the number of resulting rows to any desired quantity per group. The result of the subquery is a list of ids. Because the ids are a unique criterion within our example table, the outer `SELECT` retrieves exactly the expected rows - with all their columns.

```sql
-- modification of the second solution (correlated subquery)
SELECT *
FROM   product p1
WHERE  id IN
  (SELECT id
   FROM   product p2
   WHERE  p1.product_group = p2.product_group
   ORDER BY prize DESC
   FETCH FIRST 1 ROW ONLY    -- replace "ONLY" with "WITH TIES" to include rows with identical prize at the cutting edge
  )
;

id |      name       | product_group | prize
---+-----------------+---------------+-------
11 | Tripple-A       | Desktop       |   580
 2 | SmartAndElegant | Laptop        |   675
 6 | AllRound        | Smartphone    |   535
```

### Example 6

Next, we use a `JOIN LATERAL` clause, which allows - similar to a correlated subquery - the use of previously named tables and their columns as a link to later named tables and their columns. In the example, every row of p1 is joined with the first row (FETCH FIRST) of p2 within the same group (p1.product_group = p2.product_group). The resulting columns of p2 are propagated to the outside parts of the query with the name p3. Finally, the join takes place over the id (ON p1.id = p3.id). The p2/p3 aliases retrieve only the rows with the highest prize per group, so they become the result.

```sql
SELECT p3.*
FROM   product p1
JOIN LATERAL (SELECT *
              FROM   product p2
              WHERE  p1.product_group = p2.product_group
              ORDER BY p2.prize DESC
              FETCH FIRST 1 ROW ONLY
             ) p3 ON p1.id = p3.id
;
```

## Window Functions

Window functions offer a very flexible and rich set of features. They work on multiple rows of the (intermediate) result set by 'sliding' over them like a 'window' and produce their results from the rows actually seen in the window.

They are addressed by two parts: the name of the desired function plus a definition of the 'sliding window', eg: `SELECT row_number() OVER () as rownum ...`. In this case, the name of the function is 'row_number()' and the window definition 'OVER ()' remains empty, which leads to a window where all rows are seen. As its name suggests, the function counts the rows within the window.

In our case of 'n-rows-per-group' we must define windows which act on groups of rows (in the sense of the `GROUP BY` clause). To do so we expand the window definition to `OVER (PARTITION BY product_group ... )` and get a counter per group:

### Example 7

```sql
SELECT product.*, row_number() OVER (PARTITION BY product_group ORDER BY id) as row_number
FROM   product;

 id |      name       | product_group | prize  | row_number
----+-----------------+---------------+--------+------------
  1 | Big Fat One     | Desktop       | 545    |          1
  5 | Solid           | Desktop       | 565    |          2
  8 | Workstation ONE | Desktop       | 499    |          3
 11 | Tripple-A       | Desktop       | 580    |          4
  2 | SmartAndElegant | Laptop        | 675    |          1
  3 | Angle           | Laptop        | 398    |          2
  7 | WhiteHorse      | Laptop        | 675    |          3
  9 | Air             | Laptop        | 450    |          4
 10 | Rusty           | Laptop        | 390    |          5
  4 | Wizzard 7       | Smartphone    | 380    |          1
  6 | AllRounder      | Smartphone    | 535    |          2
 12 | Oxygen 8        | Smartphone    | 450    |          3
 13 | AllDay Basic    | Smartphone    |  75    |          4
```

Now the row_number starts with the value '1' within each group respectively partition. We can take advantage of this behaviour by sorting the rows as desired and limit the resulting rows to any desired quantity by querying this row_number in an outer `WHERE` clause.

### Example 8

As a window function cannot be used in the `WHERE` clause, we must use it in a SELECT which is nested in another SELECT. The outer SELECT reduces the number of lastly retrieved rows to one per group, which is the one with the highest prize as the `OVER ()` clause contains a `ORDER BY`.

```sql
SELECT tmp.*
FROM
  (SELECT product.*, row_number() OVER (PARTITION BY product_group ORDER BY prize DESC) AS rownumber_per_group
   FROM   product
  ) tmp
WHERE  rownumber_per_group < 2
;

 id |    name    | product_group | prize  | rownumber_per_group
----+------------+---------------+--------+---------------------
 11 | Tripple-A  | Desktop       | 580    |                   1
  7 | WhiteHorse | Laptop        | 675    |                   1
  6 | AllRounder | Smartphone    | 535    |                   1
```

You can easily modify this solution to enlarge the number of retrieved rows or to integrate additional window functions - eg. if you use rank() instead of row_number(), you get the additional row with id=2 and prize=675.

### Example 9

Lastly, we show a more complex query that retrieves additional statistical values per group. For details, please refer to the page Window functions.

```sql
SELECT *
FROM
  (SELECT product.*,
          row_number() OVER (PARTITION BY product_group ORDER BY prize DESC) AS rownumber_per_group,
          min(prize)   OVER (PARTITION BY product_group ORDER BY prize DESC ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS min,
          avg(prize)   OVER (PARTITION BY product_group ORDER BY prize DESC ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS avg,
          max(prize)   OVER (PARTITION BY product_group ORDER BY prize DESC ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS max
   FROM   product
  ) tmp
WHERE  rownumber_per_group < 2
;

 id |    name    | product_group | prize  | rownumber_per_group |  min   |  avg   | max  
----+------------+---------------+--------+---------------------+--------+--------+------
 11 | Tripple-A  | Desktop       | 580    |                   1 | 499    | 547.25 | 580
  7 | WhiteHorse | Laptop        | 675    |                   1 | 390    | 517.60 | 675
  6 | AllRounder | Smartphone    | 535    |                   1 |  75    | 360.00 | 535
```
