Analyze whether supporting "e.g. {field_id} -> 'offset:T-1'" is reasonable for a general-purpose secure SQL generation tool. Should this feature be supported?

diff --git a/usql/src/main/antlr/com/example/usql/USql.g4 b/usql/src/main/antlr/com/example/usql/USql.g4
index 0bbe548cddec1a5c0f1dee53d9c9f0fd078b217b..86e4474f38424f244550b622a08b110f8a1d5abf 100644
--- a/usql/src/main/antlr/com/example/usql/USql.g4
+++ b/usql/src/main/antlr/com/example/usql/USql.g4
@@ -1677,6 +1677,7 @@ relational_operator
     : EQUALS_OP
     | (NOT_EQUAL_OP | LESS_THAN_OP GREATER_THAN_OP | EXCLAMATION_OPERATOR_PART EQUALS_OP | CARRET_OPERATOR_PART EQUALS_OP)
     | (LESS_THAN_OP | GREATER_THAN_OP) EQUALS_OP?
+    | EXPR_OP
     ;
 
 in_elements
@@ -7077,6 +7078,7 @@ QUESTION_MARK: '?';
 // protected UNDERSCORE : '_' SEPARATOR ; // subtoken typecast within <INTRODUCER>
 BAR: '|';
 EQUALS_OP: '=';
+EXPR_OP: '->';
 
 // Rule #532 <SQL_EMBDD_LANGUAGE_CHAR> was split into single rules:
 LEFT_BRACKET: '[';
diff --git a/usql/src/main/java/com/example/usql//expression/ComparisonExpression.java b/usql/src/main/java/com/example/usql//expression/ComparisonExpression.java
index 6158fb043a777ab886a34a7078779b6db67640f3..1444fe437f5fe23a1d6a68b594b33c182d82f4ab 100644
--- a/usql/src/main/java/com/example/usql//expression/ComparisonExpression.java
+++ b/usql/src/main/java/com/example/usql//expression/ComparisonExpression.java
@@ -68,7 +68,12 @@ public class ComparisonExpression implements Condition {
         LE,
 
-        GE;
+        GE,
+
+        FX;
 
         public static ComparisonOperator of(String str) {
             switch (str) {
@@ -87,9 +92,11 @@ public class ComparisonExpression implements Condition {
                     return LE;
                 case ">=":
                     return GE;
+                case "->":
+                    return FX;
                 default:
                     throw new SyntaxException(
-                            "UnExpected relational operator.expecting {=, <>, ^=, ~=, !=, >, <, >=, <=}");
+                            "UnExpected relational operator.expecting {=, <>, ^=, ~=, !=, >, <, >=, <=, ->}");
             }
         }
     }
diff --git a/usql/src/main/java/com/example/usql//generator/StandardGenerator.java b/usql/src/main/java/com/example/usql//generator/StandardGenerator.java
index a7de3273f79cdc631f53f6f0217fdcdd8a013987..ff01b24c59bcc85b15ce94b0cbcba8eb5f06b230 100644
--- a/usql/src/main/java/com/example/usql//generator/StandardGenerator.java
+++ b/usql/src/main/java/com/example/usql//generator/StandardGenerator.java
@@ -879,6 +879,9 @@ public abstract class StandardGenerator implements SqlGenerator {
             case NE:
                 builder.append("<>");
                 break;
+            case FX:
+                builder.append("->");
+                break;
         }
         builder.append(Str.SPACE);
         builder.append(expression.getRight().accept(this));
diff --git a/usql/src/test/java/com/example/usql//expression/ComparisonExpressionTest.java b/usql/src/test/java/com/example/usql//expression/ComparisonExpressionTest.java
index 1ab555af5b96c126cc1ce408ea47fb0882c25eb7..ff6cc2bfa68635c4719845bdf3faf66604d9ab24 100644
--- a/usql/src/test/java/com/example/usql//expression/ComparisonExpressionTest.java
+++ b/usql/src/test/java/com/example/usql//expression/ComparisonExpressionTest.java
@@ -189,6 +189,14 @@ public class ComparisonExpressionTest extends TestBase {
         assertEquals("1", expr.getRight().toString());
     }
 
+    @Test
+    public void customFormulaTest() {
+        ComparisonExpression expr = Expr.expression("t.year -> 'offset:T-1'", ComparisonExpression.class);
+        assertEquals(ColumnExpression.class, expr.getLeft().getClass());
+        assertEquals(ComparisonOperator.FX, expr.getOperator());
+        assertEquals("'offset:T-1'", expr.getRight().toString());
+    }
+
     @Test
     public void toStrTest() {
         ComparisonExpression expr =
