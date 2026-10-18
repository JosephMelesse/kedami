# Eliminate Duplicates

## The Challenge

Sometimes people detect that corrupt or unwanted data exist in their database, e.g.: they forgot to create a Primary Key when using CREATE TABLE allowing time and identical values to be inserted in the key column or they recognize that values in one or the combination of multiple columns are not unique - as a violation of the business rules. The situation is commonly detected when they issue an `ALTER TABLE ... ADD PRIMARY KEY (...)` or `CREATE INDEX index_1 ON table_1 (col_1, col_2)` command.

In such cases, data must be corrected, or some rows must be deleted. As the first case depends strongly on the individual situation, we focus on the latter action. In general, the SQL command will consist of two parts: The DELETE command and a second part, where the pending rows are identified. In complex situations, it may be necessary to use more than one SQL command (which always is declarative by definition) - maybe a CURSOR with a loop over the affected rows and additional actions depending on the values in different columns.

```sql
DELETE              -- the DELETE command needs no additional specification
FROM   mytable
WHERE ...           -- identify the unwanted rows
;
```

The solutions we discuss here are closely related to the explanations in Retrieve Top N Rows per Group. Over there, we locate certain rows within groups. The same must be done here as we want to delete only dedicated rows. At least one row must be kept in each affected group.

We use the same table *product* on this page. We will eliminate all but one row where the product prize is identical to any other prize within the same product group.  The goal is that each row will have a unique combination of product_group and prize.

## Identify affected Rows

A first approach to the situation may be a 'sniffing' in the data with a `GROUP BY` clause for a listing of possibly affected rows.

```sql
SELECT product_group, prize, COUNT(*)
FROM   product
GROUP BY product_group, prize      -- create groups
HAVING COUNT(*) > 1;               -- count the number of rows within each group

 product_group | prize  | count
---------------+--------+-------
 Laptop        | 675    |     2

-- Count the number of groups where such a problem exists
SELECT COUNT(*) FROM
  (SELECT product_group, prize, COUNT(*)
   FROM   product
   GROUP BY product_group, prize
   HAVING COUNT(*) > 1
  ) tmp;

 count
-------
     1
```

But the `GROUP BY` clause is not very helpful as it is not possible to show columns other than the grouping columns and the result of some system functions like `COUNT()` (in rare cases a sort over a timestamp together with `MAX(id)` does help). The question is: how can we identify the 'right' and the 'wrong' rows? We need access to other columns of the rows to identify them. In the best case, we get access to the row's IDs.

To see such details we replace the `GROUP BY` clause by a window function (this is not the only possible solution). The following SQL command uses the same grouping over the two columns product_group and prize. And it uses a similar way to count affected rows. The main difference is that we see and have access to all columns of all rows.

```sql
SELECT product.*,
       COUNT(*) OVER (PARTITION BY product_group, prize ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) as cnt
FROM   product;

 id |      name       | product_group | prize  | cnt
----+-----------------+---------------+--------+-----
  8 | Workstation ONE | Desktop       | 499    |   1
  1 | Big Fat One     | Desktop       | 545    |   1
  5 | Solid           | Desktop       | 565    |   1
 11 | Tripple-A       | Desktop       | 580    |   1
 10 | Rusty           | Laptop        | 390    |   1
  3 | Angle           | Laptop        | 398    |   1
  9 | Air             | Laptop        | 450    |   1
  7 | WhiteHorse      | Laptop        | 675    |   2
  2 | SmartAndElegant | Laptop        | 675    |   2
 13 | AllDay Basic    | Smartphone    |  75    |   1
  4 | Wizzard 7       | Smartphone    | 380    |   1
 12 | Oxygen 8        | Smartphone    | 450    |   1
  6 | AllRounder      | Smartphone    | 535    |   1
```

This `SELECT` offers everything we need: The last column *cnt* counts the number of unique *product_group/prize* combinations. And the column *id* gives us access to every single row.

In the next step, we expand this query and shift it into a subselect (window functions cannot be used in a `WHERE` clause, only their results). The rows with a counter of '1' are not of interest, we eliminate them from the further processing, order the remaining rows in a deterministic way, and compute an additional column for the position within each group.

```sql
SELECT tmp.*
FROM   (
  SELECT product.*,
         COUNT(*)     OVER (PARTITION BY product_group, prize ORDER BY id
                            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) as cnt,
         ROW_NUMBER() OVER (PARTITION BY product_group, prize ORDER BY id) as position_within_group
  FROM   product
  ) tmp
WHERE  tmp.cnt > 1;

 id |      name       | product_group | prize  | cnt | position_within_group
----+-----------------+---------------+--------+-----+-----------------------
  2 | SmartAndElegant | Laptop        | 675    |   2 |                     1
  7 | WhiteHorse      | Laptop        | 675    |   2 |                     2
```

Up to this point our algorithm to identify problematic rows is easy, clear and the same for all use cases: create groups over the columns of interest with the `PARTITION BY` clause, count the number of rows within the groups, and eliminate groups with a counter of '1'. But now we have to decide which of the rows shall survive and which ones shall be deleted (or modified)? The answer depends strongly on the business logic, the manner in which the data was added into the table, the expectations of your customers, and much more. So you have to make your own decision.

On this page, we choose a simple solution: The row with the smallest ID shall survive; all others will be deleted. For testing purposes, we retrieve the rows we intend to delete, namely those with a position greater 1.

```sql
SELECT tmp.*
FROM  
  (SELECT product.*,
          COUNT(*)     OVER (PARTITION BY product_group, prize ORDER BY id
                             ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) as cnt,
          ROW_NUMBER() OVER (PARTITION BY product_group, prize ORDER BY id) as position_within_group
   FROM   product
  ) tmp
WHERE  tmp.cnt > 1
AND    tmp.position_within_group > 1;

 id |    name    | product_group | prize  | cnt | position_within_group
----+------------+---------------+--------+-----+-----------------------
  7 | WhiteHorse | Laptop        | 675    |   2 |                     2

-- or retrieve the rows which will survive:
...
AND    tmp.position_within_group = 1;
```

## Delete Rows

If this is what you expect, you can delete the rows in the final step. Reduce the above command to retrieve only the IDs, shift it into a subselect, and use its result as the input for a `DELETE` command.

```sql
BEGIN TRANSACTION;

DELETE
FROM   PRODUCT
WHERE  id IN
  (SELECT tmp.id
   FROM
     (SELECT product.*,
             COUNT(*)     OVER (PARTITION BY product_group, prize ORDER BY id
                                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) as cnt,
             ROW_NUMBER() OVER (PARTITION BY product_group, prize ORDER BY id) as position_within_group
      FROM   product
     ) tmp
   WHERE  tmp.cnt > 1
   AND    tmp.position_within_group > 1
  );

COMMIT;       -- or: ROLLBACK;
```
