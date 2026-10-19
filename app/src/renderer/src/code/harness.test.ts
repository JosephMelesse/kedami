// @vitest-environment node
import { loadPyodide } from 'pyodide'
import { beforeAll, describe, expect, it } from 'vitest'
import { type CodeTest, type Harness, loadHarness, type RunResult, type TestResult } from './harness'

let run: Harness

beforeAll(async () => {
  const pyodide = await loadPyodide()
  run = loadHarness(pyodide)
}, 60_000)

const TWO_SUM = `
class Solution:
    def twoSum(self, nums: List[int], target: int) -> List[int]:
        seen = {}
        for i, n in enumerate(nums):
            if target - n in seen:
                return [seen[target - n], i]
            seen[n] = i
`

const twoSumTests: CodeTest[] = [
  { args: 'nums = [2, 7, 11, 15], target = 9', expected: '[0, 1]', compare: 'equal' },
  { args: 'nums = [3, 2, 4], target = 6', expected: '[1, 2]', compare: 'equal' },
  { args: 'nums = [3, 3], target = 6', expected: '[0, 1]', compare: 'equal' }
]

function submit(code: string, method: string, tests: CodeTest[]): RunResult {
  return run({ code, method, tests, stopAtFailure: true })
}

describe('equal', () => {
  it('passes every test a correct solution answers', () => {
    const result = submit(TWO_SUM, 'twoSum', twoSumTests)
    expect(result.error).toBeNull()
    expect(result.results.map((r) => [r.passed, r.got])).toEqual([
      [true, '[0, 1]'],
      [true, '[1, 2]'],
      [true, '[0, 1]']
    ])
  })

  it('stops at the first failure on Submit and tries every test on Run', () => {
    const tests: CodeTest[] = [twoSumTests[0], { ...twoSumTests[1], expected: '[2, 1]' }, twoSumTests[2]]
    expect(submit(TWO_SUM, 'twoSum', tests).results.map((r) => r.passed)).toEqual([true, false])
    const ran = run({ code: TWO_SUM, method: 'twoSum', tests, stopAtFailure: false })
    expect(ran.results.map((r) => r.passed)).toEqual([true, false, true])
    expect(ran.results[1].got).toBe('[1, 2]')
  })

  it('compares exactly, so an answer in another order fails', () => {
    const reversed = TWO_SUM.replace('[seen[target - n], i]', '[i, seen[target - n]]')
    expect(submit(reversed, 'twoSum', twoSumTests).results[0]).toMatchObject({ passed: false, got: '[1, 0]' })
  })

  it('reads arguments written over several lines, positional arguments, strings, and inf', () => {
    const code = `
class Solution:
    def f(self, grid, word, cap=0):
        return [sum(map(sum, grid)), word.upper(), cap]
`
    const tests: CodeTest[] = [
      { args: 'grid = [[1, 2],\n        [3, 4]], word = "a,b == c"', expected: "[10, 'A,B == C', 0]", compare: 'equal' },
      { args: '[[5]], "x", inf', expected: "[5, 'X', inf]", compare: 'equal' }
    ]
    expect(submit(code, 'f', tests).results.map((r) => r.passed)).toEqual([true, true])
  })
})

describe('linked lists', () => {
  const REVERSE = `
class Solution:
    def reverseList(self, head: Optional[ListNode]) -> Optional[ListNode]:
        prev = None
        while head:
            head.next, prev, head = prev, head, head.next
        return prev
`
  const tests: CodeTest[] = [
    { args: 'head = list_node([1, 2, 3])', expected: 'list_node([3, 2, 1])', compare: 'same_list' },
    { args: 'head = list_node([])', expected: 'list_node([])', compare: 'same_list' }
  ]

  it('compares node by node and shows the returned list as values', () => {
    const result = submit(REVERSE, 'reverseList', tests)
    expect(result.results.map((r) => [r.passed, r.got])).toEqual([
      [true, '[3, 2, 1]'],
      [true, 'None']
    ])
  })

  it('fails a list that is too short or too long', () => {
    const short = submit('class Solution:\n    def reverseList(self, head):\n        return head.next', 'reverseList', tests)
    expect(short.results[0]).toMatchObject({ passed: false, got: '[2, 3]' })
    const same = submit('class Solution:\n    def reverseList(self, head):\n        return head', 'reverseList', [
      { args: 'head = list_node([1])', expected: 'list_node([])', compare: 'same_list' }
    ])
    expect(same.results[0]).toMatchObject({ passed: false, got: '[1]' })
  })

  it('fails a returned cycle without hanging, and shows it cut short', () => {
    const cycle = `
class Solution:
    def reverseList(self, head):
        head.next.next = head
        return head
`
    const result = submit(cycle, 'reverseList', tests)
    expect(result.results[0]).toMatchObject({ passed: false, got: '[1, 2, ...]' })
  })

  it("works with the student's own ListNode class", () => {
    const own = `
class ListNode:
    def __init__(self, x):
        self.val = x
        self.next = None

class Solution:
    def reverseList(self, head):
        out = None
        while head:
            node = ListNode(head.val)
            node.next, out, head = out, node, head.next
        return out
`
    expect(submit(own, 'reverseList', tests).results.map((r) => r.passed)).toEqual([true, true])
  })

  it('fails a returned Python list where a linked list is expected', () => {
    const plain = 'class Solution:\n    def reverseList(self, head):\n        return [3, 2, 1]'
    expect(submit(plain, 'reverseList', tests).results[0]).toMatchObject({ passed: false, error: null })
  })
})

describe('trees', () => {
  const INVERT = `
class Solution:
    def invertTree(self, root: Optional[TreeNode]) -> Optional[TreeNode]:
        if root:
            root.left, root.right = self.invertTree(root.right), self.invertTree(root.left)
        return root
`
  it('builds trees in level order with gaps, and shows them as LeetCode does', () => {
    const tests: CodeTest[] = [
      { args: 'root = tree_node([4, 2, 7, 1, 3, 6, 9])', expected: 'tree_node([4, 7, 2, 9, 6, 3, 1])', compare: 'same_tree' },
      { args: 'root = tree_node([1, None, 2, None, 3])', expected: 'tree_node([1, 2, None, 3])', compare: 'same_tree' },
      { args: 'root = tree_node([])', expected: 'tree_node([])', compare: 'same_tree' }
    ]
    expect(submit(INVERT, 'invertTree', tests).results.map((r) => [r.passed, r.got])).toEqual([
      [true, '[4, 7, 2, 9, 6, 3, 1]'],
      [true, '[1, 2, None, 3]'],
      [true, 'None']
    ])
  })

  it('fails a tree with the right values in the wrong shape', () => {
    const tests: CodeTest[] = [
      { args: 'root = tree_node([1, 2])', expected: 'tree_node([1, 2])', compare: 'same_tree' }
    ]
    expect(submit(INVERT, 'invertTree', tests).results[0]).toMatchObject({ passed: false, got: '[1, None, 2]' })
  })

  it('compares trees with plain values, such as a depth', () => {
    const depth = `
class Solution:
    def maxDepth(self, root):
        return 1 + max(self.maxDepth(root.left), self.maxDepth(root.right)) if root else 0
`
    const tests: CodeTest[] = [{ args: 'root = tree_node([3, 9, 20, None, None, 15, 7])', expected: '3', compare: 'equal' }]
    expect(submit(depth, 'maxDepth', tests).results[0].passed).toBe(true)
  })
})

describe('comparisons from fixes', () => {
  /** Whether code returning `value` passes a test with these arguments and expected value. */
  function passes(compare: CodeTest['compare'], args: string, expected: string, value: string): boolean {
    const code = `class Solution:\n    def f(self, **kwargs):\n        return ${value}`
    const result = submit(code, 'f', [{ args, expected, compare }])
    expect(result.error).toBeNull()
    return result.results[0].passed
  }

  it('equal reads tuples as lists at any depth', () => {
    expect(passes('equal', '', '[[0, 1], [2, 3]]', '[(0, 1), (2, 3)]')).toBe(true)
    expect(passes('equal', '', '[[0, 1], [2, 3]]', '[(1, 0), (2, 3)]')).toBe(false)
  })

  it('equal lets floats differ by 10^-5, relative to the expected value above 1', () => {
    expect(passes('equal', '', '0.25', '0.250004')).toBe(true)
    expect(passes('equal', '', '0.25', '0.2501')).toBe(false)
    expect(passes('equal', '', '1024.0', '1024.009')).toBe(true)
    expect(passes('equal', '', '1024.0', '1024.02')).toBe(false)
    expect(passes('equal', '', '[1.5, 2]', '[1.500001, 2]')).toBe(true)
    expect(passes('equal', '', 'inf', "float('inf')")).toBe(true)
    expect(passes('equal', '', '2', '2')).toBe(true)
    expect(passes('equal', '', '1', '1.000001')).toBe(true)
  })

  it('unordered takes the same items in any order, each as many times', () => {
    expect(passes('unordered', '', '[[1, 2], [3, 4]]', '[[3, 4], [1, 2]]')).toBe(true)
    expect(passes('unordered', '', '[[1, 2], [3, 4]]', '[(3, 4), (1, 2)]')).toBe(true)
    expect(passes('unordered', '', '[1, 2, 2]', '[2, 1, 2]')).toBe(true)
    expect(passes('unordered', '', '[1, 2, 2]', '[1, 1, 2]')).toBe(false)
    expect(passes('unordered', '', '[1, 2, 2]', '[1, 2]')).toBe(false)
    expect(passes('unordered', '', '[1, 2]', '[1, 2, 2]')).toBe(false)
    expect(passes('unordered', '', '[1, 2]', '{1, 2}')).toBe(false)
  })

  it('unordered fails a point given as [y, x]', () => {
    expect(passes('unordered', '', '[[1, 3], [-2, 2]]', '[[-2, 2], [3, 1]]')).toBe(false)
  })

  it('unordered_nested takes each inner list in any order too, but no deeper', () => {
    expect(passes('unordered_nested', '', '[["eat", "tea"], ["bat"]]', '[["bat"], ["tea", "eat"]]')).toBe(true)
    expect(passes('unordered_nested', '', '[[], [1], [1, 2]]', '[[2, 1], [], [1]]')).toBe(true)
    expect(passes('unordered_nested', '', '[[1, 1, 2]]', '[[1, 2, 2]]')).toBe(false)
    expect(passes('unordered_nested', '', '[[1, 2], [3]]', '[[1, 2, 3]]')).toBe(false)
    expect(passes('unordered_nested', '', '[[[1, 2]]]', '[[[2, 1]]]')).toBe(false)
  })

  it('longest_palindrome takes any palindrome in s as long as the expected one', () => {
    expect(passes('longest_palindrome', 's = "babad"', '"bab"', '"aba"')).toBe(true)
    expect(passes('longest_palindrome', 's = "babad"', '"bab"', '"bab"')).toBe(true)
    expect(passes('longest_palindrome', 's = "babad"', '"bab"', '"bad"')).toBe(false)
    expect(passes('longest_palindrome', 's = "babad"', '"bab"', '"b"')).toBe(false)
    expect(passes('longest_palindrome', 's = "babad"', '"bab"', '"cac"')).toBe(false)
  })

  it('longest_palindrome checks against the arguments as given, even if the code changed them', () => {
    const code = 'class Solution:\n    def f(self, s):\n        return "xyx"'
    const tests: CodeTest[] = [{ args: 's = "abcba"', expected: '"bcb"', compare: 'longest_palindrome' }]
    expect(submit(code, 'f', tests).results[0].passed).toBe(false)
  })

  it('course_order takes any order with every course once, each after its prerequisites', () => {
    const args = 'numCourses = 4, prerequisites = [[1, 0], [2, 0], [3, 1], [3, 2]]'
    expect(passes('course_order', args, '[0, 1, 2, 3]', '[0, 2, 1, 3]')).toBe(true)
    expect(passes('course_order', args, '[0, 1, 2, 3]', '[0, 1, 3, 2]')).toBe(false)
    expect(passes('course_order', args, '[0, 1, 2, 3]', '[0, 1, 2]')).toBe(false)
    expect(passes('course_order', args, '[0, 1, 2, 3]', '[0, 1, 1, 2, 3]')).toBe(false)
    expect(passes('course_order', args, '[0, 1, 2, 3]', '[]')).toBe(false)
  })

  it('course_order takes only an empty list when the expected list is empty', () => {
    const args = 'numCourses = 2, prerequisites = [[1, 0], [0, 1]]'
    expect(passes('course_order', args, '[]', '[]')).toBe(true)
    expect(passes('course_order', args, '[]', '[0, 1]')).toBe(false)
  })

  it('course_order uses the prerequisites as given, even if the code sorted them in place', () => {
    const code = 'class Solution:\n    def f(self, numCourses, prerequisites):\n        prerequisites.clear()\n        return [1, 0]'
    const tests: CodeTest[] = [{ args: 'numCourses = 2, prerequisites = [[1, 0]]', expected: '[0, 1]', compare: 'course_order' }]
    expect(submit(code, 'f', tests).results[0].passed).toBe(false)
  })

  it('alien_order takes any order with each letter once that puts the words in order', () => {
    const args = 'words = ["wrt", "wrf", "er", "ett", "rftt"]'
    expect(passes('alien_order', args, '"wertf"', '"wertf"')).toBe(true)
    expect(passes('alien_order', 'words = ["z", "x", "a"]', '"zxa"', '"zxa"')).toBe(true)
    expect(passes('alien_order', 'words = ["ab", "c"]', '"abc"', '"bac"')).toBe(true)
    expect(passes('alien_order', args, '"wertf"', '"wretf"')).toBe(false)
    expect(passes('alien_order', args, '"wertf"', '"werttf"')).toBe(false)
    expect(passes('alien_order', args, '"wertf"', '"wert"')).toBe(false)
  })

  it('alien_order takes only an empty string when the expected string is empty', () => {
    expect(passes('alien_order', 'words = ["abc", "ab"]', '""', '""')).toBe(true)
    expect(passes('alien_order', 'words = ["abc", "ab"]', '""', '"abc"')).toBe(false)
  })

  it('a checker fails a value of the wrong type without an error', () => {
    expect(passes('longest_palindrome', 's = "aa"', '"aa"', '["aa"]')).toBe(false)
    expect(passes('course_order', 'numCourses = 1, prerequisites = []', '[0]', '"0"')).toBe(false)
    expect(passes('alien_order', 'words = ["a"]', '"a"', 'None')).toBe(false)
  })
})

describe('errors', () => {
  it('reports code that does not compile, with its line', () => {
    const result = submit('class Solution:\n    def twoSum(self, nums, target)\n        return []', 'twoSum', twoSumTests)
    expect(result.results).toEqual([])
    expect(result.error).toContain('line 2')
    expect(result.error).toContain('SyntaxError')
  })

  it('reports code that raises while loading', () => {
    const result = submit('import nothing_here\n' + TWO_SUM, 'twoSum', twoSumTests)
    expect(result.error).toContain("ModuleNotFoundError: No module named 'nothing_here'")
    expect(result.results).toEqual([])
  })

  it('reports a missing class or method by name', () => {
    expect(submit('def twoSum(nums, target): pass', 'twoSum', twoSumTests).error).toBe(
      'Define a class Solution with a method twoSum.'
    )
    expect(submit('class Solution:\n    def other(self): pass', 'twoSum', twoSumTests).error).toBe(
      'Define a class Solution with a method twoSum.'
    )
  })

  it("fails a test that raises, showing only the student's own lines", () => {
    const code = `
class Solution:
    def twoSum(self, nums, target):
        return self.helper(nums)

    def helper(self, nums):
        return nums[99]
`
    const result = submit(code, 'twoSum', twoSumTests)
    expect(result.error).toBeNull()
    const failure = result.results[0]
    expect(failure).toMatchObject({ passed: false, got: null })
    expect(failure.error).toContain('IndexError: list index out of range')
    expect(failure.error).toContain('return nums[99]')
    expect(failure.error).toContain('solution.py')
    expect(failure.error).not.toContain('harness')
  })

  it('cuts deep recursion to its end, where the error is', () => {
    const code = 'class Solution:\n    def f(self, n):\n        return self.f(n + 1)'
    const failure = submit(code, 'f', [{ args: 'n = 0', expected: '0', compare: 'equal' }]).results[0]
    expect(failure.error).toMatch(/RecursionError: maximum recursion depth exceeded/)
    expect(failure.error!.length).toBeLessThanOrEqual(1000)
  })

  it('survives the code raising SystemExit', () => {
    const code = 'class Solution:\n    def f(self):\n        raise SystemExit(3)'
    const result = submit(code, 'f', [{ args: '', expected: '0', compare: 'equal' }])
    expect(result.results[0]).toMatchObject({ passed: false })
    expect(result.results[0].error).toContain('SystemExit')
    expect(submit(TWO_SUM, 'twoSum', twoSumTests).results.every((r) => r.passed)).toBe(true)
  })

  it('reads escapes Python warns about, as the dataset writes them', () => {
    const code = 'class Solution:\n    def f(self, s):\n        return len(s)'
    const result = submit(code, 'f', [{ args: 's = "a\\:b"', expected: '4', compare: 'equal' }])
    expect(result.results[0].passed).toBe(true)
  })

  it("marks a test that can't be read as failed without blaming the code", () => {
    const tests: CodeTest[] = [{ args: 'nums = [1, 2', expected: '[0]', compare: 'equal' }, twoSumTests[0]]
    const result = run({ code: TWO_SUM, method: 'twoSum', tests, stopAtFailure: false })
    expect(result.results[0]).toEqual({ passed: false, got: null, output: '', error: "This test can't be read." })
    expect(result.results[1].passed).toBe(true)
  })
})

describe('output', () => {
  it('keeps what the code prints while loading and during each test apart', () => {
    const code = `print("loading")\n${TWO_SUM.replace('seen = {}', 'seen = {}\n        print("nums", nums)')}`
    const result = run({ code, method: 'twoSum', tests: twoSumTests.slice(0, 2), stopAtFailure: false })
    expect(result.output).toBe('loading\n')
    expect(result.results.map((r) => r.output)).toEqual(['nums [2, 7, 11, 15]\n', 'nums [3, 2, 4]\n'])
  })

  it('keeps the end of long output and the start of a long returned value', () => {
    const code = `
class Solution:
    def f(self):
        for i in range(500):
            print(i)
        return list(range(1000))
`
    const result = submit(code, 'f', [{ args: '', expected: '[]', compare: 'equal' }]).results[0]
    expect(result.output.length).toBe(1000)
    expect(result.output.startsWith('...')).toBe(true)
    expect(result.output.endsWith('498\n499\n')).toBe(true)
    expect(result.got!.length).toBe(1000)
    expect(result.got!.startsWith('[0, 1, 2')).toBe(true)
    expect(result.got!.endsWith('...')).toBe(true)
  })
})

describe('progress', () => {
  it('reports each result as it finishes, in order, up to the first failure on Submit', () => {
    const tests: CodeTest[] = [twoSumTests[0], { ...twoSumTests[1], expected: '[2, 1]' }, twoSumTests[2]]
    const reported: TestResult[] = []
    const result = run({ code: TWO_SUM, method: 'twoSum', tests, stopAtFailure: true }, (r) => reported.push(r))
    expect(reported).toEqual(result.results)
    expect(reported.map((r) => r.passed)).toEqual([true, false])
  })

  it('reports nothing when the code fails before any test', () => {
    const reported: TestResult[] = []
    run({ code: 'class Solution(', method: 'twoSum', tests: twoSumTests, stopAtFailure: true }, (r) => reported.push(r))
    expect(reported).toEqual([])
  })
})

describe('namespace', () => {
  it("provides LeetCode's imports and helpers", () => {
    const code = `
class Solution:
    def f(self, nums: List[int]) -> int:
        counts = Counter(nums)
        heap = list(counts.values())
        heapify(heap)
        return heappop(heap) + bisect_left([1, 2, 3], 2) + gcd(4, 6) + len(defaultdict(int)) + (inf > 0) + datetime.date(2024, 1, 1).day - 1
`
    expect(submit(code, 'f', [{ args: 'nums = [1, 1, 2]', expected: '5', compare: 'equal' }]).results[0].passed).toBe(true)
  })

  it('provides sortedcontainers, as LeetCode does, both preloaded and by import', () => {
    const code = `
from sortedcontainers import SortedDict

class Solution:
    def f(self, nums: List[int]) -> List[int]:
        sl = SortedList(nums)
        sl.add(0)
        return list(sl) + list(SortedDict({2: 0, 1: 0}))
`
    const tests: CodeTest[] = [{ args: 'nums = [3, 1, 2]', expected: '[0, 1, 2, 3, 1, 2]', compare: 'equal' }]
    expect(submit(code, 'f', tests).results[0]).toMatchObject({ passed: true, error: null })
  })

  it('starts each request fresh, so nothing carries over from an earlier one', () => {
    const counting = `
calls = 0

class Solution:
    def f(self):
        global calls
        calls += 1
        return calls
`
    const tests: CodeTest[] = [{ args: '', expected: '1', compare: 'equal' }]
    expect(submit(counting, 'f', tests).results[0].passed).toBe(true)
    expect(submit(counting, 'f', tests).results[0].passed).toBe(true)
    const result = submit('class Solution:\n    def f(self):\n        return calls', 'f', tests)
    expect(result.results[0].error).toContain("NameError: name 'calls' is not defined")
  })

  it("doesn't let the code change the names tests are built with", () => {
    const code = `
def list_node(values):
    return "replaced"

class Solution:
    def f(self, head):
        return head.val
`
    const tests: CodeTest[] = [{ args: 'head = list_node([7])', expected: '7', compare: 'equal' }]
    expect(submit(code, 'f', tests).results[0].passed).toBe(true)
  })
})
