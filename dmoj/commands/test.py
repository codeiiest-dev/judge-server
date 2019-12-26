import os
import sys
import traceback
from operator import itemgetter

import yaml

from dmoj import executors
from dmoj.commands.base_command import Command
from dmoj.error import InvalidCommandException
from dmoj.judgeenv import get_problem_root, get_supported_problems
from dmoj.testsuite import Tester
from dmoj.utils.ansi import ansi_style, print_ansi

all_executors = executors.executors


class ProblemTester(Tester):
    def test_problem(self, problem):
        self.output(ansi_style('Testing problem #ansi[%s](cyan|bold)...') % problem)
        fails = 0
        with open(os.path.join(get_problem_root(problem), 'init.yml'), 'r') as f:
            config = yaml.safe_load(f.read())

        if not config or 'tests' not in config or not config['tests']:
            self.output(ansi_style('\t#ansi[Skipped](magenta|bold) - No tests found'))

        for test in config['tests']:
            # Do this check here as we need some way to identify the test
            if 'source' not in test:
                continue

            test_name = test.get('label', test['source'])
            self.output(ansi_style('\tRunning test #ansi[%s](yellow|bold)') % test_name)
            try:
                test_fails = self.run_test(problem, test)
            except Exception:
                fails += 1
                self.output(ansi_style('\t#ansi[Test failed with exception:](red|bold)'))
                self.output(traceback.format_exc())
            else:
                self.output(ansi_style('\tResult of test #ansi[%s](yellow|bold): ') % test_name +
                            ansi_style(['#ansi[Failed](red|bold)', '#ansi[Success](green|bold)'][not test_fails]))
                fails += test_fails

        return fails

    def _check_targets(targets):
        if 'posix' in targets:
            return True
        if 'freebsd' in sys.platform:
            if 'freebsd' in targets:
                return True
            if not sys.platform.startswith('freebsd') and 'kfreebsd' in targets:
                return True
        elif sys.platform.startswith('linux') and 'linux' in targets:
            return True
        return False

    def run_test(self, problem, config):
        if 'skip' in config and config['skip']:
            self.output(ansi_style('\t\t#ansi[Skipped](magenta|bold) - Test skipped'))
            return 0

        if 'targets' in config and not self._check_targets(config['targets']):
            return 0

        try:
            language = config['lang']
            if language not in all_executors:
                self.output(ansi_style('\t\t#ansi[Skipped](magenta|bold) - Language not supported'))
                return 0

            time = config['timelimit']
            memory = config['memlimit']
        except KeyError:
            self.output(ansi_style('\t\t#ansi[Skipped](magenta|bold) - Invalid configuration'))
            return 0

        with open(os.path.join(get_problem_root(problem), config['source'])) as f:
            source = f.read()

        codes_all, codes_cases = self.parse_expect(config.get('expect', 'AC'),
                                                   config.get('cases', {}),
                                                   self.parse_expected_codes)
        feedback_all, feedback_cases = self.parse_expect(config.get('feedback'),
                                                         config.get('feedback_cases', {}),
                                                         self.parse_feedback)

        def output_case(data):
            self.output('\t\t' + data.strip())

        self.sub_id += 1
        self.manager.set_expected(codes_all, codes_cases, feedback_all, feedback_cases)
        self.judge.begin_grading(self.sub_id, problem, language, source, time, memory, False, False, blocking=True,
                                 report=output_case)
        return self.manager.failed


class TestCommand(Command):
    name = 'test'
    help = 'Runs tests on a problem.'

    def _populate_parser(self):
        self.arg_parser.add_argument('problem_id', help='id of problem to test')

    def execute(self, line):
        args = self.arg_parser.parse_args(line)

        problem_id = args.problem_id

        if problem_id not in map(itemgetter(0), get_supported_problems()):
            raise InvalidCommandException("unknown problem '%s'" % problem_id)

        tester = ProblemTester()
        fails = tester.test_problem(problem_id)
        print()
        print('Test complete')
        if fails:
            print_ansi('#ansi[A total of %d test(s) failed](red|bold)' % fails)
        else:
            print_ansi('#ansi[All tests passed.](green|bold)')
