# SELECT: Case Expression

Sometimes it's necessary to translate stored values (or values to be stored) from one representation to another. Suppose there is a column *status* with legal values from 0 to 9, but the end-users should receive strings that explain the meaning of the numeric values in short, eg.: 'ordered', 'delivered', 'back delivery', 'out of stock', ... . The recommended way to do this is a separate table where the numeric values maps to the explanatory strings. Notwithstanding this, application developers may favor a solution within an application server.

The CASE expression, which is shown on this page, is a technique for solving the described situation as part of a SELECT, INSERT or UPDATE command as well as solving additional problems. As part of the language, it's a powerful term that can be applied at plenty of places within SQL commands. On this page, we focus on its use together with the SELECT command. The strategy and syntax for CASE within INSERT and UPDATE are equivalent and are presented over there. In comparison with the recommended technique of a separate table for the translation, the CASE expression is much more flexible (which is not an advantage in all cases).

## Two Examples

```sql
-- Technical term: "simple case" 
-- Select id, contact_type in a translated version and contact_value
SELECT id,
       CASE contact_type
         WHEN 'fixed line' THEN 'Phone'
         WHEN 'mobile'     THEN 'Phone'
         ELSE                   'Not a telephone number'
       END AS 'contact_type',
       contact_value
FROM   contact;
```

The CASE expression is introduced with its keyword CASE and runs up to the END keyword. In this first example, it specifies a column name and a series of WHEN/THEN clauses with an optional ELSE clause. The WHEN/THEN clauses are compared and evaluated against the values of the named column, one after the other. If none of them hits, the ELSE clause applies. If there is no ELSE clause and none of the WHEN/THEN clauses hit, the NULL special marker will be applied.

The comparison between the values of the column and the fixed values within the WHEN/THEN clause is done solely by "=" (equals). This is a good starting point, but real applications need more than that. Therefore there is a variant of the CASE.

```sql
-- Technical term: "searched case" 
-- Select persons name, weight and a denomination of the weight 
SELECT firstname,
       lastname,
       weight,
       CASE
         WHEN (weight IS NULL OR weight = 0) THEN 'weight is unknown'
         WHEN weight < 40                    THEN 'lightweight'
         WHEN weight BETWEEN 40 AND 85       THEN 'medium'
         ELSE                                     'heavyweight'
       END AS 'weight'
FROM   person;
```

The crucial point is the direct succession of the two keywords CASE and WHEN. There is **no** column name between them. In this variant, there must be a complete expression, which evaluates to one of the 3-value-logic terms *true*, *false* or *unknown*, between each WHEN and THEN. Now it is possible to use all the comparisons and boolean operators as they are known by the WHERE clause. It is even possible to compare different columns or function calls with each other.

## Syntax

There are the two variants *simple case* and *searched case*.

```sql
-- "simple case" performs successive comparisons using the equal operator: <column_name> = <expression_x>
CASE <column_name>
  WHEN <expression_1> THEN <result_1>
  WHEN <expression_2> THEN <result_2>
  ...
  ELSE                     <default_result>  -- optional
END

-- "searched case" is recognised by 'nothing' between CASE and first WHEN
CASE
  WHEN <condition_1> THEN <result_1>
  WHEN <condition_2> THEN <result_2>
  ...
  ELSE                    <default_result>  -- optional
END
```

The *simple case* is limited to one column and the use of the equal operator, whereas the *searched case* may evaluate arbitrary columns of the (intermediate) result with arbitrary operators, functions or predicates.

## Typical Use Cases

The use of CASE expressions is not limited to projections (the column list between SELECT and FROM). As the clause evaluates to a value, it can be applied as a substitution for values at several places within SQL commands. In the following, we offer some examples.

ORDER BY clause

Sort contact values in the order: all fixed lines, all mobile phones, all emails, all icq's. Within each group sort over the contact values.

```sql
SELECT *
FROM   contact
ORDER  BY
       -- a "simple case" construct as substitution for a column name
       CASE contact_type
         WHEN 'fixed line' THEN 0
         WHEN 'mobile'     THEN 1
         WHEN 'email'      THEN 2
         WHEN 'icq'        THEN 3
         ELSE                   4
       END,
       contact_value;
```

In the next example, persons are ordered by weight classes, within the classes by their name.

```sql
-- order by weight classes
SELECT firstname, lastname, weight,
       CASE
         WHEN (weight IS NULL OR weight = 0) THEN 'weight is unknown'
         WHEN weight < 40                    THEN 'lightweight'
         WHEN weight BETWEEN 40 AND 85       THEN 'medium'
         ELSE                                     'heavyweight'
       END
FROM   person
ORDER  BY
       -- a "searched case" construct with IS NULL, BETWEEN and 'less than'.
       CASE
         WHEN (weight IS NULL OR weight = 0) THEN 0
         WHEN weight < 40                    THEN 1
         WHEN weight BETWEEN 40 AND 85       THEN 2
         ELSE                                     3 
       END, lastname, firstname;
```

WHERE clause

Within the WHERE clauses, there may occur fixed values or column names. CASE expressions can be used as a substitution for them. In the example, persons receive a discount on their weight depending on their place of birth (consider it as a theoretical example). Thus Mr. Goldstein, with its 95 kg, counts only with 76 kg and is not part of the result set.

```sql
SELECT *
FROM   person
WHERE  CASE
         -- Modify weight depending on place of birth.
         WHEN place_of_birth = 'Dallas'   THEN weight * 0.8
         WHEN place_of_birth = 'Richland' THEN weight * 0.9
         ELSE                                  weight
       END > 80
OR     weight < 20; -- any other condition
```

## Exercises

**Exercise:** Show firstname, lastname and the gender of all persons. Consider Larry, Tom, James, John, Elias, Yorgos, Victor as 'male',
Lisa as 'female' and all others as 'unknown gender'. Use a *simple case* expression.

**Solution:**

```sql
SELECT firstname, lastname,
       CASE firstname
         WHEN 'Larry'   THEN 'male'
         WHEN 'Tom'     THEN 'male'
         WHEN 'James'   THEN 'male'
         WHEN 'John'    THEN 'male'
         WHEN 'Elias'   THEN 'male'
         WHEN 'Yorgos'  THEN 'male'
         WHEN 'Victor'  THEN 'male'
         WHEN 'Lisa'    THEN 'female'
         ELSE                'unknown gender'
       END
FROM   person;
```

**Exercise:** Use a *searched case* expression to solve the previous question.

**Solution:**

```sql
SELECT firstname, lastname,
       CASE
         WHEN firstname in ('Larry', 'Tom', 'James', 'John', 'Elias', 'Yorgos', 'Victor')
                                     THEN 'male'
         WHEN firstname = 'Lisa'     THEN 'female'
         ELSE                             'unknown gender'
       END
FROM   person;
```

**Exercise:** Show firstname, lastname and a classification of all persons. Classify persons according to the length of their firstname. Call the class 'short name' if character_length(firstname) < 4, 'medium length' if < 6, 'long name' else.

**Solution:**

```sql
-- Hint: Some implementations use a different function name: length() or len().
SELECT firstname, lastname,
       CASE 
         WHEN CHARACTER_LENGTH(firstname) < 4 THEN 'short name'
         WHEN CHARACTER_LENGTH(firstname) < 6 THEN 'medium length'
         ELSE                                      'long name'
       END
FROM   person;
```

**Exercise:** Count the number of short, medium and long names of the above exercise.

**Solution:**

```sql
-- Hint: Some implementations use a different function name: length() or len().
SELECT SUM(CASE 
             WHEN CHARACTER_LENGTH(firstname) < 4 THEN 1
             ELSE                                      0
           END) as short_names,
       SUM(CASE 
             WHEN CHARACTER_LENGTH(firstname) between 4 and 5 THEN 1
             ELSE                                                  0
           END) as medium,
       SUM(CASE 
             WHEN CHARACTER_LENGTH(firstname) > 5 THEN 1
             ELSE                                      0
           END) as long_names
FROM   person;
```
